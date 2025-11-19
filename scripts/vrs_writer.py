"""VRS Writer module for creating VRS files from sensor data.

This module provides a Pythonic interface to the pyvrs_writer C++ bindings,
which wrap the VRS C++ library's RecordFileWriter class.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import pyvrs_writer
except ImportError as e:
    raise ImportError(
        "pyvrs_writer module not found. "
        "Please build and install pyvrs_writer from pyvrs_writer/ directory."
    ) from e


class VRSWriter:
    """VRS file writer with Pythonic interface and context manager support.

    This class wraps the pyvrs_writer C++ bindings to provide a simple
    interface for creating VRS files and writing sensor data.

    Example:
        >>> with VRSWriter("output.vrs") as writer:
        ...     writer.add_stream(1001, "RGB Camera")
        ...     writer.write_configuration(1001, {"width": 640, "height": 480})
        ...     writer.write_data(1001, 0.0, b"image_data")
    """

    def __init__(self, filepath: Path | str) -> None:
        """Initialize VRS writer and create VRS file.

        Args:
            filepath: Path to the VRS file to create (Path or str)

        Raises:
            ValueError: If filepath is invalid
            RuntimeError: If VRS file creation fails
        """
        if isinstance(filepath, str):
            filepath = Path(filepath)

        if not isinstance(filepath, Path):
            raise ValueError(f"filepath must be Path or str, got {type(filepath).__name__}")

        self._filepath = filepath
        self._writer: Any = None  # pyvrs_writer.VRSWriter instance
        self._stream_ids: set[int] = set()  # Track added stream IDs

        try:
            self._writer = pyvrs_writer.VRSWriter(str(filepath))  # type: ignore[attr-defined]
        except Exception as e:
            raise RuntimeError(f"Failed to create VRS file '{filepath}': {e}") from e

    def __enter__(self) -> VRSWriter:
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

    def add_stream(self, stream_id: int, stream_name: str) -> None:
        """Add a new stream to the VRS file.

        Args:
            stream_id: Unique stream identifier (positive integer)
            stream_name: Human-readable stream name

        Raises:
            ValueError: If stream_id is invalid or already exists
            RuntimeError: If VRS file is not open or stream addition fails
        """
        if not self.is_open():
            raise RuntimeError("VRS file is not open")

        if not isinstance(stream_id, int) or stream_id <= 0:
            raise ValueError(f"stream_id must be a positive integer, got {stream_id}")

        if not isinstance(stream_name, str):
            raise ValueError(f"stream_name must be str, got {type(stream_name).__name__}")

        # Check for duplicate stream ID
        if stream_id in self._stream_ids:
            raise ValueError(f"Stream ID {stream_id} already exists. Stream IDs must be unique.")

        try:
            assert self._writer is not None
            # Encode stream_id in stream_name (flavor) for later retrieval by VRSReader
            # Format: "stream_name|id:stream_id"
            encoded_name = f"{stream_name}|id:{stream_id}"
            self._writer.add_stream(stream_id, encoded_name)
            self._stream_ids.add(stream_id)  # Track successfully added stream
        except Exception as e:
            raise RuntimeError(f"Failed to add stream {stream_id} '{stream_name}': {e}") from e

    def write_configuration(self, stream_id: int, config_data: dict[str, Any]) -> None:
        """Write a Configuration record for the specified stream.

        Configuration records should be written once per stream after add_stream().

        Args:
            stream_id: Target stream ID
            config_data: Configuration parameters as JSON-serializable dictionary

        Raises:
            ValueError: If stream_id doesn't exist or config_data is not serializable
            RuntimeError: If VRS file is not open or write fails
        """
        if not self.is_open():
            raise RuntimeError("VRS file is not open")

        if not isinstance(stream_id, int) or stream_id <= 0:
            raise ValueError(f"stream_id must be a positive integer, got {stream_id}")

        # Check if stream ID exists
        if stream_id not in self._stream_ids:
            raise ValueError(f"Stream ID {stream_id} does not exist. Call add_stream() first.")

        if not isinstance(config_data, dict):
            raise ValueError(f"config_data must be dict, got {type(config_data).__name__}")

        try:
            config_json = json.dumps(config_data)
        except (TypeError, ValueError) as e:
            raise ValueError(f"config_data is not JSON-serializable: {e}") from e

        try:
            assert self._writer is not None
            self._writer.write_configuration(stream_id, config_json)
        except Exception as e:
            raise RuntimeError(f"Failed to write configuration for stream {stream_id}: {e}") from e

    def write_data(self, stream_id: int, timestamp: float, data: bytes | list[int]) -> None:
        """Write a Data record for the specified stream.

        Data records can be written multiple times per stream with increasing
        timestamps.

        Args:
            stream_id: Target stream ID
            timestamp: Timestamp in seconds (relative to recording start)
            data: Data payload as bytes or list of integers (0-255)

        Raises:
            ValueError: If stream_id doesn't exist, timestamp is negative, or data is empty
            RuntimeError: If VRS file is not open or write fails
        """
        if not self.is_open():
            raise RuntimeError("VRS file is not open")

        if not isinstance(stream_id, int) or stream_id <= 0:
            raise ValueError(f"stream_id must be a positive integer, got {stream_id}")

        # Check if stream ID exists
        if stream_id not in self._stream_ids:
            raise ValueError(f"Stream ID {stream_id} does not exist. Call add_stream() first.")

        if not isinstance(timestamp, (int, float)):
            raise ValueError(f"timestamp must be numeric, got {type(timestamp).__name__}")

        if timestamp < 0:
            raise ValueError(f"timestamp must be non-negative, got {timestamp}")

        # Convert bytes to list[int] if necessary (pyvrs_writer expects list[int])
        if isinstance(data, bytes):
            data_list = list(data)
        elif isinstance(data, list):
            data_list = data
        else:
            raise ValueError(f"data must be bytes or list[int], got {type(data).__name__}")

        if not data_list:
            raise ValueError("data must not be empty")

        try:
            assert self._writer is not None
            self._writer.write_data(stream_id, float(timestamp), data_list)
        except Exception as e:
            raise RuntimeError(
                f"Failed to write data for stream {stream_id} at {timestamp}s: {e}"
            ) from e

    def close(self) -> None:
        """Close the VRS file.

        This must be called to finalize the VRS file. Alternatively, use the
        context manager (with statement) for automatic cleanup.

        Raises:
            RuntimeError: If close fails
        """
        if self._writer is not None and self.is_open():
            try:
                self._writer.close()
            except Exception as e:
                raise RuntimeError(f"Failed to close VRS file: {e}") from e

    def is_open(self) -> bool:
        """Check if the VRS file is currently open.

        Returns:
            True if the file is open, False otherwise
        """
        if self._writer is None:
            return False
        try:
            return bool(self._writer.is_open())
        except Exception:
            return False
