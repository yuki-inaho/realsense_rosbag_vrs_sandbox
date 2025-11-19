"""VRS Reader module for reading VRS files.

This module provides a Pythonic interface to the PyVRS library,
which reads VRS (Virtual Reality Stream) files created by Meta.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

try:
    import pyvrs
except ImportError as e:
    raise ImportError(
        "pyvrs module not found. Please install with: uv add vrs"
    ) from e


class VRSReader:
    """VRS file reader with Pythonic interface and context manager support.

    This class wraps the pyvrs.SyncVRSReader to provide a simple interface
    for reading VRS files.

    Example:
        >>> with VRSReader("input.vrs") as reader:
        ...     stream_ids = reader.get_stream_ids()
        ...     config = reader.read_configuration(stream_ids[0])
        ...     for record in reader.read_data_records(stream_ids[0]):
        ...         print(record["timestamp"], record["data"])
    """

    def __init__(self, filepath: Path | str) -> None:
        """Initialize VRS reader and open VRS file.

        Args:
            filepath: Path to the VRS file to read (Path or str)

        Raises:
            FileNotFoundError: If file does not exist
            ValueError: If filepath is invalid or file is not a valid VRS file
            RuntimeError: If VRS file opening fails
        """
        if isinstance(filepath, str):
            filepath = Path(filepath)

        if not isinstance(filepath, Path):
            raise ValueError(
                f"filepath must be Path or str, got {type(filepath).__name__}"
            )

        if not filepath.exists():
            raise FileNotFoundError(f"VRS file not found: {filepath}")

        self._filepath = filepath
        self._reader: Any = None  # pyvrs.SyncVRSReader instance
        self._stream_id_mapping: dict[int, str] = {}  # user_id -> vrs_stream_id

        try:
            self._reader = pyvrs.SyncVRSReader(str(filepath))
            # Cache stream ID mapping at initialization (no iteration required)
            for vrs_stream_id in self._reader.stream_ids:
                info = self._reader.get_stream_info(vrs_stream_id)
                flavor = info.get("flavor", "")
                if "|id:" in flavor:
                    try:
                        user_id = int(flavor.split("|id:")[-1])
                        self._stream_id_mapping[user_id] = vrs_stream_id
                    except ValueError:
                        pass
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
            stream_ids = []
            for vrs_stream_id in self._reader.stream_ids:
                info = self._reader.get_stream_info(vrs_stream_id)
                flavor = info.get("flavor", "")

                # Extract user stream_id from flavor
                # Format: "stream_name|id:stream_id"
                if "|id:" in flavor:
                    try:
                        user_stream_id = int(flavor.split("|id:")[-1])
                        stream_ids.append(user_stream_id)
                    except ValueError:
                        # Fallback: use VRS instance ID
                        if "-" in vrs_stream_id:
                            stream_ids.append(int(vrs_stream_id.split("-")[-1]))
                else:
                    # No encoded ID, use VRS instance ID
                    if "-" in vrs_stream_id:
                        stream_ids.append(int(vrs_stream_id.split("-")[-1]))

            return sorted(stream_ids)
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
                                return json.loads(config_json_str)
                            except json.JSONDecodeError:
                                # Return as string if not valid JSON
                                return {"config_json": config_json_str}
                        else:
                            # Return metadata directly if no config_json field
                            return metadata
                    else:
                        # No metadata blocks, return empty dict
                        return {}

            # If no configuration found, raise error
            raise ValueError(f"No configuration record found for stream {stream_id}")
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(
                f"Failed to read configuration for stream {stream_id}: {e}"
            ) from e

    def read_data_records(self, stream_id: int) -> Iterator[dict[str, Any]]:
        """Read all data records for the specified stream.

        Args:
            stream_id: Target stream ID (user-specified)

        Yields:
            Dictionary with 'timestamp' and 'data' keys for each record

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

            for record in self._reader:
                # Note: record.record_type is a string, not enum
                if record.stream_id == vrs_stream_id and record.record_type == "data":
                    # Get data from custom_blocks (CUSTOM block)
                    data = b""
                    if record.n_custom_blocks > 0:
                        # custom_blocks[0] contains the raw data
                        custom_block = record.custom_blocks[0]
                        if isinstance(custom_block, bytes):
                            data = custom_block
                        elif hasattr(custom_block, 'data'):
                            data = custom_block.data
                        # Otherwise, data remains empty bytes

                    yield {
                        "timestamp": record.timestamp,
                        "data": data,
                    }
        except ValueError:
            raise
        except Exception as e:
            raise RuntimeError(
                f"Failed to read data records for stream {stream_id}: {e}"
            ) from e

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
            raise RuntimeError(
                f"Failed to count records for stream {stream_id}: {e}"
            ) from e

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
