"""VRS Reader module for reading VRS files.

This module provides a Pythonic interface to the PyVRS library,
which reads VRS (Virtual Reality Stream) files created by Meta.
"""

from __future__ import annotations

import base64
import json
import struct
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

from scripts.image_codec_storage import (
    CODEC_IMAGE,
    CODEC_SCHEMA_VERSION,
    IMAGE_CODEC_TAG,
    ImageRecordDecoder,
    decode_payload_text,
)
from scripts.image_codecs import (
    CodecRegistry,
    ImageCodecDescriptor,
    ImageCodecError,
    ImageSpec,
    default_codec_registry,
)
from scripts.vrs_schema import (
    IMU_VECTOR,
    IMU_VECTOR_FIELD,
    NATIVE_IMAGE,
    OPAQUE_BYTES,
    OPAQUE_BYTES_FIELD,
    PAYLOAD_ENCODING_TAG,
    SCHEMA_VERSION,
    SCHEMA_VERSION_TAG,
)

try:
    import pyvrs
except ImportError as e:
    raise ImportError("pyvrs module not found. Please install with: uv add vrs") from e


class VRSReader:
    """VRS file reader with Pythonic interface and context manager support.

    This class wraps the pyvrs.SyncVRSReader to provide a simple interface
    for reading VRS files. Encoded images are restored using the persisted codec
    descriptor and an explicitly supplied registry (built-ins by default).

    Example:
        >>> with VRSReader("input.vrs") as reader:
        ...     stream_ids = reader.get_stream_ids()
        ...     config = reader.read_configuration(stream_ids[0])
        ...     for record in reader.read_data_records(stream_ids[0]):
        ...         print(record["timestamp"], record["data"])
    """

    def __init__(
        self, filepath: Path | str, *, codec_registry: CodecRegistry | None = None
    ) -> None:
        """Open a VRS file. Custom codecs must be registered by trusted application code."""
        if isinstance(filepath, str):
            filepath = Path(filepath)

        if not isinstance(filepath, Path):
            raise ValueError(f"filepath must be Path or str, got {type(filepath).__name__}")

        if not filepath.exists():
            raise FileNotFoundError(f"VRS file not found: {filepath}")

        self._codec_registry = (codec_registry or default_codec_registry()).copy()
        self._filepath = filepath
        self._reader: Any = None  # pyvrs.SyncVRSReader instance
        self._stream_id_mapping: dict[int, str] = {}  # user_id -> vrs_stream_id

        try:
            self._reader = pyvrs.SyncVRSReader(str(filepath))
            # Keep the original RGB/depth values; PyVRS can otherwise normalize images.
            self._reader.set_image_conversion(pyvrs.ImageConversion.OFF)
            # Cache stream ID mapping at initialization (no iteration required)
            for vrs_stream_id in self._reader.stream_ids:
                info = self._reader.get_stream_info(vrs_stream_id)
                user_id = self._get_tagged_user_stream_id(vrs_stream_id)
                if user_id is None:
                    user_id = self._parse_user_stream_id(info.get("flavor", ""))
                if user_id is None and "-" in vrs_stream_id:
                    try:
                        user_id = int(vrs_stream_id.split("-")[-1])
                    except ValueError:
                        user_id = None
                if user_id is not None:
                    self._stream_id_mapping[user_id] = vrs_stream_id
        except Exception as e:
            raise RuntimeError(f"Failed to open VRS file '{filepath}': {e}") from e

    def __enter__(self) -> VRSReader:
        """Context manager entry.

        Returns:
            self
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Context manager exit. Automatically closes the file.

        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)
        """
        self.close()

    def get_stream_ids(self) -> list[int]:
        """Get list of all stream IDs in the VRS file.

        Extracts user-specified stream IDs from VRS stream flavors (encoded as "name|id:1001").

        Returns:
            List of user-specified stream IDs

        Raises:
            RuntimeError: If reader is not open
        """
        if self._reader is None:
            raise RuntimeError("VRS file is not open")

        try:
            return sorted(self._stream_id_mapping)
        except Exception as e:
            raise RuntimeError(f"Failed to get stream IDs: {e}") from e

    def _get_vrs_stream_id(self, user_stream_id: int) -> str:
        """Convert user stream_id to VRS stream_id using cached mapping.

        Args:
            user_stream_id: User-specified stream ID

        Returns:
            VRS stream ID (format: "RecordableTypeId-InstanceId")

        Raises:
            ValueError: If stream_id not found
        """
        if user_stream_id in self._stream_id_mapping:
            return self._stream_id_mapping[user_stream_id]

        raise ValueError(f"Stream ID {user_stream_id} not found")

    @staticmethod
    def _parse_user_stream_id(flavor: str) -> int | None:
        """Extract ``|id:1001`` from a stream flavor."""
        if "|id:" not in flavor:
            return None
        suffix = flavor.split("|id:", maxsplit=1)[1]
        value = suffix.split("|", maxsplit=1)[0]
        try:
            return int(value)
        except ValueError:
            return None

    def _stream_tags(self, vrs_stream_id: str) -> dict[str, str]:
        if self._reader is None:
            return {}
        tags = getattr(self._reader, "stream_tags", {})
        if isinstance(tags, dict):
            stream_tags = tags.get(vrs_stream_id, {})
            if isinstance(stream_tags, dict):
                return stream_tags
        return {}

    def _get_tagged_user_stream_id(self, vrs_stream_id: str) -> int | None:
        tags = self._stream_tags(vrs_stream_id)
        value = tags.get("user_stream_id")
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def read_configuration(self, stream_id: int) -> dict[str, Any]:
        """Read configuration record for the specified stream.

        Args:
            stream_id: Target stream ID (user-specified)

        Returns:
            Configuration data as dictionary

        Raises:
            ValueError: If stream_id doesn't exist
            RuntimeError: If reader is not open or read fails
        """
        if self._reader is None:
            raise RuntimeError("VRS file is not open")

        if not isinstance(stream_id, int):
            raise ValueError(f"stream_id must be int, got {type(stream_id).__name__}")

        try:
            # Convert user stream_id to VRS stream_id
            vrs_stream_id = self._get_vrs_stream_id(stream_id)
            tags = self._stream_tags(vrs_stream_id)
            if "config_json" in tags:
                try:
                    return cast(dict[str, Any], json.loads(tags["config_json"]))
                except json.JSONDecodeError:
                    return {"config_json": tags["config_json"]}

            # Iterate through all records and find configuration for the stream
            for record in self._reader:
                # Note: record.record_type is a string, not enum
                if record.stream_id == vrs_stream_id and record.record_type == "configuration":
                    # Get data from metadata_blocks (DataLayout)
                    if record.n_metadata_blocks > 0:
                        metadata = record.metadata_blocks[0]
                        # Extract config_json field from metadata
                        if "config_json" in metadata:
                            config_json_str = metadata["config_json"]
                            try:
                                # Try to decode as JSON
                                return cast(dict[str, Any], json.loads(config_json_str))
                            except json.JSONDecodeError:
                                # Return as string if not valid JSON
                                return {"config_json": config_json_str}
                        else:
                            # Return metadata directly if no config_json field
                            return cast(dict[str, Any], metadata)
                    else:
                        # No metadata blocks, return empty dict
                        return {}

            # If no configuration found, raise error
            raise ValueError(f"No configuration record found for stream {stream_id}")
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to read configuration for stream {stream_id}: {e}") from e

    def read_data_records(self, stream_id: int) -> Iterator[dict[str, Any]]:
        """Yield timestamps and restored bytes; JPEG output is necessarily lossy.

        Existing native/legacy payloads keep their old interpretation. Codec
        selection for new encoded images comes from the file, not caller guesses.
        """
        if self._reader is None:
            raise RuntimeError("VRS file is not open")

        if not isinstance(stream_id, int):
            raise ValueError(f"stream_id must be int, got {type(stream_id).__name__}")

        try:
            vrs_stream_id = self._get_vrs_stream_id(stream_id)
            tags = self._stream_tags(vrs_stream_id)
            decoder = None
            if tags.get(PAYLOAD_ENCODING_TAG) == CODEC_IMAGE:
                self._codec_descriptor(tags)
                decoder = ImageRecordDecoder(tags[IMAGE_CODEC_TAG], self._codec_registry)
            for record in self._reader:
                if record.stream_id == vrs_stream_id and record.record_type == "data":
                    yield {
                        "timestamp": record.timestamp,
                        "data": self._record_payload(record, tags, decoder),
                    }
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to read data records for stream {stream_id}: {e}") from e

    @staticmethod
    def _codec_descriptor(tags: dict[str, str]) -> ImageCodecDescriptor:
        if tags.get(SCHEMA_VERSION_TAG) != CODEC_SCHEMA_VERSION:
            raise ImageCodecError("Encoded images require VRS sandbox schema 3")
        try:
            descriptor = ImageCodecDescriptor.from_json(tags[IMAGE_CODEC_TAG])
            config = json.loads(tags["config_json"])
            if descriptor.image != ImageSpec.from_config(config):
                raise ImageCodecError("Codec descriptor disagrees with sensor configuration")
            return descriptor
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ImageCodecError("Missing or invalid encoded-image stream tags") from exc

    def read_encoded_image_records(self, stream_id: int) -> Iterator[dict[str, Any]]:
        """Extract compressed bytes and their descriptor without needing the decoder plugin.

        Only schema-3 encoded image streams support this method. It never returns
        an undecoded buffer from ``read_data_records`` as though it were pixels.
        """
        if self._reader is None:
            raise RuntimeError("VRS file is not open")
        vrs_stream_id = self._get_vrs_stream_id(stream_id)
        tags = self._stream_tags(vrs_stream_id)
        if tags.get(PAYLOAD_ENCODING_TAG) != CODEC_IMAGE:
            raise ImageCodecError("Stream does not contain encoded images")
        descriptor = self._codec_descriptor(tags)
        for record in self._reader:
            if record.stream_id == vrs_stream_id and record.record_type == "data":
                if record.n_metadata_blocks != 1 or record.n_image_blocks:
                    raise ImageCodecError("Invalid encoded-image record blocks")
                yield {
                    "timestamp": record.timestamp,
                    "descriptor": descriptor,
                    "data": decode_payload_text(record.metadata_blocks[0][OPAQUE_BYTES_FIELD]),
                }

    @staticmethod
    def _record_payload(
        record: Any, tags: dict[str, str], image_decoder: ImageRecordDecoder | None = None
    ) -> bytes:
        """Decode versioned sensor records and historical byte-oriented files."""
        metadata = record.metadata_blocks[0] if record.n_metadata_blocks else {}
        schema_version = tags.get(SCHEMA_VERSION_TAG)
        if schema_version is not None:
            if schema_version not in (SCHEMA_VERSION, CODEC_SCHEMA_VERSION):
                raise ValueError(f"Unsupported VRS sandbox schema version: {schema_version}")
            encoding = tags.get(PAYLOAD_ENCODING_TAG)
            if encoding == CODEC_IMAGE:
                if record.n_metadata_blocks != 1 or record.n_image_blocks:
                    raise ImageCodecError("Invalid encoded-image record blocks")
                if image_decoder is None:
                    VRSReader._codec_descriptor(tags)
                    image_decoder = ImageRecordDecoder(
                        tags[IMAGE_CODEC_TAG], default_codec_registry()
                    )
                return image_decoder.decode(metadata.get(OPAQUE_BYTES_FIELD))
            if encoding == IMU_VECTOR:
                values = metadata.get(IMU_VECTOR_FIELD, ())
                if len(values) != 3:
                    raise ValueError("An IMU record must contain exactly three components")
                return struct.pack("<ddd", *values)
            if encoding == OPAQUE_BYTES:
                return base64.b64decode(metadata[OPAQUE_BYTES_FIELD], validate=True)
            if encoding != NATIVE_IMAGE:
                raise ValueError(f"Unknown VRS payload encoding: {encoding}")
            if record.n_image_blocks != 1:
                raise ValueError("A native image record must contain exactly one image block")
            return cast(bytes, record.image_blocks[0].tobytes())

        # Before schema v2, C++ writers used CUSTOM blocks and the first PyVRS
        # adapter stored opaque bytes in a one-row GREY8 image. Keep both readable.
        if record.n_custom_blocks:
            block = record.custom_blocks[0]
            if isinstance(block, bytes):
                return block
            if hasattr(block, "tobytes"):
                return cast(bytes, block.tobytes())
            if hasattr(block, "data"):
                return bytes(block.data)
            return bytes(block)
        if getattr(record, "n_image_blocks", 0):
            block = record.image_blocks[0]
            data = block.tobytes() if hasattr(block, "tobytes") else bytes(block.data)
            payload_len = metadata.get("some_string_int_map", {}).get("payload_len")
            if isinstance(payload_len, int):
                data = data[:payload_len]
            return cast(bytes, data)
        return b""

    def get_record_count(self, stream_id: int) -> int:
        """Get the number of data records for the specified stream.

        Args:
            stream_id: Target stream ID (user-specified)

        Returns:
            Number of data records

        Raises:
            ValueError: If stream_id doesn't exist
            RuntimeError: If reader is not open
        """
        if self._reader is None:
            raise RuntimeError("VRS file is not open")

        try:
            # Convert user stream_id to VRS stream_id
            vrs_stream_id = self._get_vrs_stream_id(stream_id)

            count = 0
            for record in self._reader:
                # Note: record.record_type is a string, not enum
                if record.stream_id == vrs_stream_id and record.record_type == "data":
                    count += 1
            return count
        except Exception as e:
            raise RuntimeError(f"Failed to count records for stream {stream_id}: {e}") from e

    def close(self) -> None:
        """Close the VRS file.

        This method is called automatically when using the context manager.
        """
        if self._reader is not None:
            try:
                self._reader.close()
            except Exception:
                # Ignore close errors
                pass
            finally:
                self._reader = None
