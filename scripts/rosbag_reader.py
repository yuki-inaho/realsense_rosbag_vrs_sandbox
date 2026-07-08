"""ROSbag file reading utilities.

This module provides a clean interface for reading ROS bag files using the rosbags library.
Follows the Single Responsibility Principle (SRP) by focusing solely on bag file I/O.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

from rosbags.rosbag1 import Reader


class RosbagReader:
    """Reader for ROS bag files with a clean, Pythonic interface.

    This class wraps the rosbags library to provide a simplified API for
    reading ROS bag files. It supports context manager protocol for safe
    resource management.

    Example:
        >>> with RosbagReader(Path("data.bag")) as reader:
        ...     topics = reader.get_available_topics()
        ...     for msg in reader.read_messages(topics[0]):
        ...         print(msg["timestamp"])
    """

    def __init__(self, bag_path: Path) -> None:
        """Initialize the ROSbag reader.

        Args:
            bag_path: Path to the ROSbag file

        Raises:
            FileNotFoundError: If the bag file does not exist
            ValueError: If the path is not a file
        """
        if not bag_path.exists():
            raise FileNotFoundError(f"Bag file not found: {bag_path}")
        if not bag_path.is_file():
            raise ValueError(f"Path is not a file: {bag_path}")

        self.bag_path = bag_path
        self._reader: Reader | None = None

    def __enter__(self) -> "RosbagReader":
        """Enter context manager."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context manager and cleanup resources."""
        if self._reader is not None:
            self._reader.close()
            self._reader = None

    def _get_reader(self) -> Reader:
        """Get or create the Reader instance.

        Returns:
            Reader instance for the bag file
        """
        if self._reader is None:
            self._reader = Reader(self.bag_path)
            self._reader.open()
        return self._reader

    def get_available_topics(self) -> list[str]:
        """Get list of all topics in the bag file.

        Returns:
            List of topic names
        """
        reader = self._get_reader()
        return [conn.topic for conn in reader.connections]

    def get_topics_info(self) -> dict[str, dict[str, Any]]:
        """Get detailed information about all topics.

        Returns:
            Dictionary mapping topic names to their metadata including
            message type and message count
        """
        reader = self._get_reader()
        topics_info = {}
        for conn in reader.connections:
            topics_info[conn.topic] = {
                "msgtype": conn.msgtype,
                "msgcount": conn.msgcount,
            }
        return topics_info

    def get_duration(self) -> float:
        """Get the duration of the bag file in seconds.

        Returns:
            Duration in seconds
        """
        reader = self._get_reader()
        return cast(float, reader.duration / 1e9)  # Convert nanoseconds to seconds

    def get_message_count(self, topic: str) -> int:
        """Get the number of messages for a specific topic.

        Args:
            topic: Topic name

        Returns:
            Number of messages on the topic
        """
        reader = self._get_reader()
        for conn in reader.connections:
            if conn.topic == topic:
                return cast(int, conn.msgcount)
        return 0

    def filter_topics(self, pattern: str) -> list[str]:
        """Filter topics by a pattern string.

        Args:
            pattern: String pattern to search for in topic names

        Returns:
            List of matching topic names
        """
        topics = self.get_available_topics()
        return [topic for topic in topics if pattern in topic]

    def read_messages(self, topic: str) -> Iterator[dict[str, Any]]:
        """Read messages from a specific topic.

        Args:
            topic: Topic name to read from

        Yields:
            Dictionary containing:
            - 'timestamp' (int): nanoseconds since epoch
            - 'data' (bytes): raw message data
            - 'msgtype' (str): message type name
            - 'connection' (Connection): connection object

        Example:
            >>> for msg in reader.read_messages("/camera/image"):
            ...     print(f"Time: {msg['timestamp']}, Type: {msg['msgtype']}")
        """
        reader = self._get_reader()

        # Filter connections for the requested topic
        connections = [conn for conn in reader.connections if conn.topic == topic]

        if not connections:
            # Topic not found, yield nothing
            return

        for connection, timestamp, rawdata in reader.messages(connections=connections):
            yield {
                "timestamp": timestamp,  # nanoseconds since epoch
                "data": rawdata,  # raw bytes
                "msgtype": connection.msgtype,
                "connection": connection,
            }
