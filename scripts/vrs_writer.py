"""VRS writer adapter backed by the official PyVRS writer package.

The public API keeps the repository's converter-facing writer contract:
``add_stream()``, ``write_configuration()``, ``write_data()``, ``close()``,
and ``is_open()``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

_OFFICIAL_STREAM_FACTORY = "sample_with_image"
_USER_STREAM_ID_TAG = "user_stream_id"
_USER_STREAM_NAME_TAG = "user_stream_name"
_CONFIG_JSON_TAG = "config_json"


def load_official_writer_backend() -> tuple[str, type[Any], Any]:
    """Load the official PyVRS writer, patching v1.2.2 export gaps.

    The vrs 1.2.2 wheel ships ``pyvrs.writer`` but does not re-export a few
    native binding symbols from ``pyvrs.__init__``. It also uses the old
    ``CompressionPreset.Zmedium`` enum name. Patch those names before import so
    the official writer module can be used without modifying site-packages.
    """
    import pyvrs
    import vrsbindings

    for name in ("RecordFormat", "Stream", "Writer"):
        if not hasattr(pyvrs, name):
            setattr(pyvrs, name, getattr(vrsbindings, name))

    if not hasattr(pyvrs.CompressionPreset, "Zmedium"):
        pyvrs.CompressionPreset.Zmedium = pyvrs.CompressionPreset.ZSTD_MEDIUM

    from pyvrs.writer import VRSWriter as OfficialVRSWriter

    return "pyvrs.writer.VRSWriter", OfficialVRSWriter, pyvrs


@dataclass
class _StreamState:
    name: str
    stream: Any | None = None
    config_data: dict[str, Any] | None = None
    config_record_written: bool = False
    payload_width: int | None = None


class VRSWriter:
    """VRS file writer with the repository's historical writer API."""

    backend_name = "pyvrs.writer.VRSWriter"

    def __init__(self, filepath: Path | str, compression: str = "lz4") -> None:
        if isinstance(filepath, str):
            filepath = Path(filepath)

        if not isinstance(filepath, Path):
            raise ValueError(f"filepath must be Path or str, got {type(filepath).__name__}")

        self._backend_name, writer_cls, self._pyvrs = load_official_writer_backend()
        self.backend_name = self._backend_name
        self._filepath = filepath
        self._writer = writer_cls(str(filepath))
        self._compression_preset = self._resolve_compression(compression)
        self._stream_states: dict[int, _StreamState] = {}
        self._max_record_timestamp = 0.0
        self._has_pending_records = False
        self._closed = False

    def __enter__(self) -> VRSWriter:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        self.close()

    def add_stream(self, stream_id: int, stream_name: str) -> None:
        """Register a logical stream id and name."""
        self._validate_open()
        self._validate_stream_id(stream_id)

        if not isinstance(stream_name, str):
            raise ValueError(f"stream_name must be str, got {type(stream_name).__name__}")

        if stream_id in self._stream_states:
            raise ValueError(f"Stream ID {stream_id} already exists. Stream IDs must be unique.")

        self._stream_states[stream_id] = _StreamState(name=self._logical_stream_name(stream_name))

    def write_configuration(self, stream_id: int, config_data: dict[str, Any]) -> None:
        """Write a Configuration record and persist the original config as a stream tag."""
        self._validate_open()
        self._validate_stream_id(stream_id)

        if not isinstance(config_data, dict):
            raise ValueError(f"config_data must be dict, got {type(config_data).__name__}")

        state = self._state_for(stream_id)
        if state.config_record_written:
            raise ValueError(f"Configuration for stream {stream_id} has already been written.")

        try:
            json.dumps(config_data)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"config_data is not JSON-serializable: {exc}") from exc

        state.config_data = config_data

    def write_data(self, stream_id: int, timestamp: float, data: bytes | list[int]) -> None:
        """Write a Data record for the specified stream."""
        self._validate_open()
        self._validate_stream_id(stream_id)

        if not isinstance(timestamp, (int, float)):
            raise ValueError(f"timestamp must be numeric, got {type(timestamp).__name__}")

        if timestamp < 0:
            raise ValueError(f"timestamp must be non-negative, got {timestamp}")

        if isinstance(data, bytes):
            payload = data
        elif isinstance(data, list):
            try:
                payload = bytes(data)
            except ValueError as exc:
                raise ValueError("data list must contain integers in range 0-255") from exc
        else:
            raise ValueError(f"data must be bytes or list[int], got {type(data).__name__}")

        if not payload:
            raise ValueError("data must not be empty")

        state = self._state_for(stream_id)
        self._ensure_official_stream(stream_id)
        if state.stream is None:
            raise RuntimeError(f"stream {stream_id} was not initialized")
        if not state.config_record_written:
            state.config_data = state.config_data or {}
            self._write_official_configuration(stream_id, payload_width=len(payload))
        elif state.payload_width != len(payload):
            self._write_official_configuration(
                stream_id,
                payload_width=len(payload),
                timestamp=float(timestamp),
            )

        metadata = state.stream.get_data_record_metadata()
        metadata["camera_id"] = int(stream_id)
        metadata["room_temperature"] = 0.0
        metadata["some_string"] = ""
        metadata["some_string_int_map"] = {"payload_len": len(payload)}
        metadata["doubles"] = [0.0, 0.0, 0.0]

        payload_array = np.frombuffer(payload, dtype=np.uint8).copy()
        state.stream.create_data_record(float(timestamp), metadata, payload_array)
        self._max_record_timestamp = max(self._max_record_timestamp, float(timestamp))
        self._has_pending_records = True

    def close(self) -> None:
        if not self._closed:
            for stream_id, state in self._stream_states.items():
                if state.config_data is not None and not state.config_record_written:
                    self._ensure_official_stream(stream_id)
                    self._write_official_configuration(stream_id, payload_width=1)
            if self._has_pending_records:
                self._writer.flush_records(self._max_record_timestamp)
            else:
                self._writer.flush_records(0.0)
            self._writer.close()
            self._closed = True

    def is_open(self) -> bool:
        return not self._closed

    def _resolve_compression(self, compression: str) -> Any:
        normalized = compression.lower()
        presets = self._pyvrs.CompressionPreset
        if normalized == "none":
            return presets.NONE
        if normalized == "lz4":
            return presets.LZ4_FAST
        if normalized == "zstd":
            return presets.ZSTD_MEDIUM
        raise ValueError(
            f"Unsupported compression '{compression}'. Expected one of: none, lz4, zstd."
        )

    def _validate_open(self) -> None:
        if not self.is_open():
            raise RuntimeError("VRS file is not open")

    @staticmethod
    def _validate_stream_id(stream_id: int) -> None:
        if not isinstance(stream_id, int) or stream_id <= 0:
            raise ValueError(f"stream_id must be a positive integer, got {stream_id}")

    @staticmethod
    def _logical_stream_name(stream_name: str) -> str:
        return stream_name.split("|id:", maxsplit=1)[0]

    def _state_for(self, stream_id: int) -> _StreamState:
        if stream_id not in self._stream_states:
            raise ValueError(f"Stream ID {stream_id} does not exist. Call add_stream() first.")
        return self._stream_states[stream_id]

    def _ensure_official_stream(self, stream_id: int) -> None:
        state = self._state_for(stream_id)
        if state.stream is not None:
            return

        state.stream = self._writer.create_stream(
            _OFFICIAL_STREAM_FACTORY,
            compression=self._compression_preset,
        )
        state.stream.set_tag(_USER_STREAM_ID_TAG, str(stream_id))
        state.stream.set_tag(_USER_STREAM_NAME_TAG, state.name)
        state.stream.set_tag(
            _CONFIG_JSON_TAG,
            json.dumps(state.config_data or {}, separators=(",", ":"), sort_keys=True),
        )

    def _write_official_configuration(
        self,
        stream_id: int,
        payload_width: int,
        timestamp: float = 0.0,
    ) -> None:
        state = self._state_for(stream_id)
        assert state.stream is not None

        metadata = state.stream.get_config_record_metadata()
        metadata["image_width"] = int(max(payload_width, 1))
        metadata["image_height"] = 1
        metadata["image_pixel_format"] = self._pyvrs.PixelFormat.GREY8.value
        state.stream.create_config_record(timestamp, metadata)
        state.payload_width = int(max(payload_width, 1))
        state.config_record_written = True
        self._max_record_timestamp = max(self._max_record_timestamp, timestamp)
        self._has_pending_records = True
