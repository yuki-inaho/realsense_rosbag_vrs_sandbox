"""Versioned RGB-D/IMU writing through the official ``vrsbindings`` package.

The converter-facing API is retained, while the official native writer avoids
PyVRS 1.2.2's incomplete high-level imports without modifying third-party modules.
All streams and tags are fixed before the first data record. Records are drained
periodically so memory use does not grow with the duration of a recording.
"""

from __future__ import annotations

import base64
import json
import math
import struct
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.image_codec_storage import (
    CODEC_IMAGE,
    CODEC_SCHEMA_VERSION,
    IMAGE_CODEC_TAG,
    encode_payload_text,
)
from scripts.image_codecs import (
    CodecRegistry,
    CodecSpec,
    ImageCodecDescriptor,
    ImageEncoder,
    ImageSpec,
    default_codec_registry,
    encode_pixels,
)
from scripts.vrs_schema import (
    CONFIG_JSON_TAG,
    IMU_VECTOR,
    IMU_VECTOR_FIELD,
    NATIVE_IMAGE,
    OPAQUE_BYTES,
    OPAQUE_BYTES_FIELD,
    PAYLOAD_ENCODING_TAG,
    SCHEMA_VERSION,
    SCHEMA_VERSION_TAG,
    USER_STREAM_ID_TAG,
    USER_STREAM_NAME_TAG,
)

_DEFAULT_FLUSH_BYTES = 16 * 1024 * 1024
_DEFAULT_FLUSH_RECORDS = 256
_MAX_BACKGROUND_QUEUE_BYTES = 64 * 1024 * 1024
_BACKGROUND_QUEUE_TIMEOUT_SECONDS = 30.0
_MAX_STREAM_ID = (1 << 31) - 1


def load_official_writer_backend() -> tuple[str, type[Any], Any]:
    """Return the official native writer without patching ``pyvrs`` exports."""
    import vrsbindings

    return "vrsbindings.Writer", vrsbindings.Writer, vrsbindings


@dataclass
class _StreamState:
    name: str
    config_json: str = "{}"
    payload_encoding: str = OPAQUE_BYTES
    image_spec: ImageSpec | None = None
    image_descriptor: ImageCodecDescriptor | None = None
    image_encoder: ImageEncoder | None = None
    stream: Any = None
    data_format: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class _Payload:
    byte_count: int
    image: Any = None
    vector: tuple[float, float, float] | None = None
    text: str = ""


class VRSWriter:
    """Write images and typed IMU metadata using official VRS factories.

    ``image_codecs`` selects an independent codec per logical stream ID. Omitted
    streams retain native raw images and schema 2. Encoded images use the explicit
    schema-3 carrier; ``compression`` still controls only VRS record compression.

    ``add_stream`` and ``write_configuration`` must precede the first
    ``write_data`` call. Data timestamps are globally nondecreasing; equal
    timestamps across or within streams are allowed. Unknown byte payloads are
    explicitly base64-encoded in a metadata string, never disguised as images.

    ``flush_bytes`` and ``flush_records`` bound pending payloads/record counts;
    one record may exceed the byte threshold. The native background queue is
    drained separately. These are buffering limits, not a bound on process RSS.
    """

    backend_name = "vrsbindings.Writer"

    def __init__(
        self,
        filepath: Path | str,
        compression: str = "lz4",
        *,
        flush_bytes: int = _DEFAULT_FLUSH_BYTES,
        flush_records: int = _DEFAULT_FLUSH_RECORDS,
        image_codecs: Mapping[int, CodecSpec] | None = None,
        codec_registry: CodecRegistry | None = None,
    ) -> None:
        if isinstance(filepath, str):
            filepath = Path(filepath)
        if not isinstance(filepath, Path):
            raise ValueError(f"filepath must be Path or str, got {type(filepath).__name__}")
        for name, value in (("flush_bytes", flush_bytes), ("flush_records", flush_records)):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        self._image_codecs = dict(image_codecs or {})
        for stream_id, codec in self._image_codecs.items():
            self._validate_stream_id(stream_id)
            if not isinstance(codec, CodecSpec):
                raise ValueError("image_codecs values must be CodecSpec instances")
        self._codec_registry = (codec_registry or default_codec_registry()).copy()

        self.backend_name, writer_cls, self._bindings = load_official_writer_backend()
        self._compression_preset = self._resolve_compression(compression)
        self._filepath = filepath
        self._writer = writer_cls()
        self._stream_states: dict[int, _StreamState] = {}
        self._flush_bytes = flush_bytes
        self._flush_records = flush_records
        self._pending_bytes = 0
        self._pending_records = 0
        self._last_timestamp: float | None = None
        self._started = False
        self._closed = False

    def __enter__(self) -> VRSWriter:
        self._validate_open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if exc_type is None:
            self.close()
        else:
            self._abort()

    def add_stream(self, stream_id: int, stream_name: str) -> None:
        """Register a logical stream before writing starts."""
        self._validate_setup()
        self._validate_stream_id(stream_id)
        if not isinstance(stream_name, str) or not stream_name:
            raise ValueError("stream_name must be a non-empty string")
        if stream_id in self._stream_states:
            raise ValueError(f"Stream ID {stream_id} already exists. Stream IDs must be unique.")
        self._stream_states[stream_id] = _StreamState(name=stream_name.split("|id:", maxsplit=1)[0])

    def write_configuration(self, stream_id: int, config_data: dict[str, Any]) -> None:
        """Snapshot sensor settings; validate and select the image codec before file creation."""
        self._validate_setup()
        state = self._state_for(stream_id)
        if not isinstance(config_data, dict):
            raise ValueError(f"config_data must be dict, got {type(config_data).__name__}")
        try:
            serialized = json.dumps(
                config_data, separators=(",", ":"), sort_keys=True, allow_nan=False
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"config_data is not JSON-serializable: {exc}") from exc

        descriptor = None
        encoder = None
        image_keys = {"width", "height", "encoding"}
        if image_keys <= config_data.keys():
            spec = self._image_spec(config_data)
            codec = self._image_codecs.get(stream_id, CodecSpec())
            encoder, lossless = self._codec_registry.encoder(codec, spec)
            encoding = NATIVE_IMAGE if (codec.name, codec.version) == ("raw", 1) else CODEC_IMAGE
            if encoding == CODEC_IMAGE:
                descriptor = ImageCodecDescriptor(spec, codec, lossless)
        else:
            if stream_id in self._image_codecs:
                raise ValueError(f"Image codec selected for non-image stream {stream_id}")
            spec = None
            encoding = (
                IMU_VECTOR
                if config_data.get("sensor_type") in ("accelerometer", "gyroscope")
                else OPAQUE_BYTES
            )
        state.config_json = serialized
        state.image_spec = spec
        state.image_descriptor = descriptor
        state.image_encoder = encoder
        state.payload_encoding = encoding

    def write_data(self, stream_id: int, timestamp: float, data: bytes | list[int]) -> None:
        """Append one data record, preserving real image and IMU types."""
        self._validate_open()
        state = self._state_for(stream_id)
        record_timestamp = self._validate_timestamp(timestamp)
        payload = self._prepare_payload(state, self._payload_bytes(data))
        try:
            self._start()

            # Drain the preceding batch before accepting a record that would exceed
            # its byte budget. A single large image is flushed immediately below.
            if (
                self._pending_records
                and self._pending_bytes + payload.byte_count > self._flush_bytes
            ):
                self._flush()
            if payload.image is not None:
                state.stream.createRecord(record_timestamp, state.data_format, payload.image)
            else:
                if payload.vector is not None:
                    state.metadata[IMU_VECTOR_FIELD].set(list(payload.vector))
                else:
                    state.metadata[OPAQUE_BYTES_FIELD].set(payload.text)
                state.stream.createRecord(record_timestamp, state.data_format)

            self._last_timestamp = record_timestamp
            self._pending_records += 1
            self._pending_bytes += payload.byte_count
            if (
                self._pending_bytes >= self._flush_bytes
                or self._pending_records >= self._flush_records
            ):
                self._flush()
        except BaseException:
            self._abort()
            raise

    def close(self) -> None:
        """Finish the last timestamp and close the file; repeated calls are safe."""
        if self._closed:
            return
        try:
            self._start()
            self._flush()
        except BaseException:
            self._abort()
            raise
        else:
            self._check_status(self._writer.close(), "close")
        finally:
            self._closed = True

    def is_open(self) -> bool:
        return not self._closed

    def _abort(self) -> None:
        """Stop native threads after a failure without masking that failure."""
        if not self._closed:
            try:
                self._writer.close()
            except Exception:
                pass
            finally:
                self._closed = True

    def _start(self) -> None:
        if self._started:
            return
        for stream_id in self._image_codecs:
            if self._state_for(stream_id).image_spec is None:
                raise ValueError(f"Image configuration missing for stream {stream_id}")
        file_version = (
            CODEC_SCHEMA_VERSION
            if any(s.payload_encoding == CODEC_IMAGE for s in self._stream_states.values())
            else SCHEMA_VERSION
        )
        self._writer.setTag(SCHEMA_VERSION_TAG, file_version)
        for stream_id, state in self._stream_states.items():
            native_image = state.payload_encoding == NATIVE_IMAGE
            factory = "sample_with_image" if native_image else "sample"
            stream = self._writer.createStream(factory)
            stream.setCompression(self._compression_preset)
            version = CODEC_SCHEMA_VERSION if state.image_descriptor else SCHEMA_VERSION
            for key, value in (
                (SCHEMA_VERSION_TAG, version),
                (USER_STREAM_ID_TAG, str(stream_id)),
                (USER_STREAM_NAME_TAG, state.name),
                (CONFIG_JSON_TAG, state.config_json),
                (PAYLOAD_ENCODING_TAG, state.payload_encoding),
            ):
                stream.setTag(key, value)
            if state.image_descriptor is not None:
                stream.setTag(IMAGE_CODEC_TAG, state.image_descriptor.to_json())
            configuration = stream.createRecordFormat(self._bindings.RecordType.CONFIGURATION)
            members = configuration.getMembers()[0]
            spec = state.image_spec
            members["image_width"].set(spec.width if spec else 0)
            members["image_height"].set(spec.height if spec else 0)
            members["image_pixel_format"].set(
                getattr(self._bindings.PixelFormat, spec.pixel_format).value if spec else 0
            )
            stream.createRecord(0.0, configuration)
            data_format = stream.createRecordFormat(self._bindings.RecordType.DATA)
            metadata = data_format.getMembers()[0]
            metadata["camera_id"].set(stream_id)
            metadata["room_temperature"].set(0.0)
            metadata[IMU_VECTOR_FIELD].set([0.0, 0.0, 0.0])
            metadata[OPAQUE_BYTES_FIELD].set("")
            metadata["some_string_int_map"].set({})
            state.stream = stream
            state.data_format = data_format
            state.metadata = metadata
        self._check_status(self._writer.create(str(self._filepath)), "create")
        self._started = True

    def _flush(self) -> None:
        self._wait_for_background_queue()
        # VRS uses a timestamp boundary. Moving to the next representable value
        # also flushes records exactly at the last timestamp (including 0.0).
        boundary = math.nextafter(self._last_timestamp or 0.0, math.inf)
        self._check_status(self._writer.writeRecords(boundary), "writeRecords")
        self._pending_bytes = 0
        self._pending_records = 0
        self._wait_for_background_queue()

    def _wait_for_background_queue(self) -> None:
        deadline = time.monotonic() + _BACKGROUND_QUEUE_TIMEOUT_SECONDS
        while self._writer.getBackgroundThreadQueueByteSize() > _MAX_BACKGROUND_QUEUE_BYTES:
            if time.monotonic() >= deadline:
                raise RuntimeError("VRS background write queue did not drain within 30 seconds")
            time.sleep(0.01)

    def _check_status(self, status: int, operation: str) -> None:
        if status != 0:
            raise RuntimeError(
                f"Official VRS {operation} failed for '{self._filepath}' (status {status})"
            )

    def _resolve_compression(self, compression: str) -> Any:
        if not isinstance(compression, str):
            raise ValueError("compression must be one of: none, lz4, zstd")
        presets = self._bindings.CompressionPreset
        options = {"none": presets.NONE, "lz4": presets.LZ4_FAST, "zstd": presets.ZSTD_MEDIUM}
        try:
            return options[compression.lower()]
        except KeyError as exc:
            raise ValueError("compression must be one of: none, lz4, zstd") from exc

    def _validate_open(self) -> None:
        if self._closed:
            raise RuntimeError("VRS file is not open")

    def _validate_setup(self) -> None:
        self._validate_open()
        if self._started:
            raise RuntimeError("Streams and configuration are fixed after the first data record")

    @staticmethod
    def _validate_stream_id(stream_id: int) -> None:
        if (
            isinstance(stream_id, bool)
            or not isinstance(stream_id, int)
            or not 0 < stream_id <= _MAX_STREAM_ID
        ):
            raise ValueError(f"stream_id must be an integer between 1 and {_MAX_STREAM_ID}")

    def _state_for(self, stream_id: int) -> _StreamState:
        self._validate_stream_id(stream_id)
        if stream_id not in self._stream_states:
            raise ValueError(f"Stream ID {stream_id} does not exist. Call add_stream() first.")
        return self._stream_states[stream_id]

    def _validate_timestamp(self, timestamp: float) -> float:
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
            raise ValueError("timestamp must be a finite non-negative number")
        try:
            value = float(timestamp)
        except (ValueError, OverflowError) as exc:
            raise ValueError("timestamp must be a finite non-negative number") from exc
        if not math.isfinite(value) or value < 0:
            raise ValueError("timestamp must be a finite non-negative number")
        if self._last_timestamp is not None and value < self._last_timestamp:
            raise ValueError("Data timestamps must be globally nondecreasing")
        return value

    @staticmethod
    def _payload_bytes(data: bytes | list[int]) -> bytes:
        if isinstance(data, bytes):
            payload = data
        elif isinstance(data, list):
            try:
                payload = bytes(data)
            except (ValueError, TypeError, OverflowError) as exc:
                raise ValueError("data list must contain integers in range 0-255") from exc
        else:
            raise ValueError(f"data must be bytes or list[int], got {type(data).__name__}")
        if not payload:
            raise ValueError("data must not be empty")
        return payload

    @staticmethod
    def _prepare_payload(state: _StreamState, payload: bytes) -> _Payload:
        if state.image_spec is not None:
            spec = state.image_spec
            if len(payload) != spec.byte_count:
                raise ValueError(
                    f"Image payload is {len(payload)} bytes; expected {spec.byte_count} "
                    f"for {spec.width}x{spec.height} {spec.pixel_format}"
                )
            image = spec.array_from_bytes(payload)
            if state.payload_encoding == CODEC_IMAGE:
                if state.image_encoder is None:
                    raise RuntimeError("Image encoder has not been configured")
                encoded = encode_payload_text(encode_pixels(state.image_encoder, image, spec))
                return _Payload(byte_count=len(encoded), text=encoded)
            return _Payload(byte_count=len(payload), image=image)
        if state.payload_encoding == IMU_VECTOR:
            if len(payload) != 24:
                raise ValueError("IMU payload must contain exactly three little-endian doubles")
            x, y, z = struct.unpack("<ddd", payload)
            return _Payload(byte_count=24, vector=(x, y, z))
        encoded = base64.b64encode(payload).decode("ascii")
        return _Payload(byte_count=len(encoded), text=encoded)

    @staticmethod
    def _image_spec(config: dict[str, Any]) -> ImageSpec:
        return ImageSpec.from_config(config)
