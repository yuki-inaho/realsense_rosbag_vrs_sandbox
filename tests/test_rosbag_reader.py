"""Tests for ROSbag reading functionality."""

from pathlib import Path

import pytest


class TestRosbagReader:
    """Test cases for ROSbag file reading."""

    def test_rosbag_reader_initialization(self, rosbag_path: Path) -> None:
        """Test that RosbagReader can be initialized with a valid path."""
        from scripts.rosbag_reader import RosbagReader

        reader = RosbagReader(rosbag_path)

        assert reader is not None
        assert reader.bag_path == rosbag_path

    def test_get_available_topics(self, rosbag_path: Path) -> None:
        """Test retrieving list of available topics from ROSbag."""
        from scripts.rosbag_reader import RosbagReader

        reader = RosbagReader(rosbag_path)
        topics = reader.get_available_topics()

        assert isinstance(topics, list)
        assert len(topics) > 0
        # Check for expected RealSense topics
        assert any("Depth" in topic for topic in topics)
        assert any("Color" in topic or "RGB" in topic for topic in topics)

    def test_get_topic_info(self, rosbag_path: Path) -> None:
        """Test retrieving topic metadata (type, count)."""
        from scripts.rosbag_reader import RosbagReader

        reader = RosbagReader(rosbag_path)
        topics_info = reader.get_topics_info()

        assert isinstance(topics_info, dict)
        assert len(topics_info) > 0

        # Check that each topic has message type and count
        for topic, info in topics_info.items():
            assert "msgtype" in info
            assert "msgcount" in info
            assert isinstance(info["msgcount"], int)
            assert info["msgcount"] >= 0

    def test_get_duration(self, rosbag_path: Path) -> None:
        """Test retrieving bag file duration."""
        from scripts.rosbag_reader import RosbagReader

        reader = RosbagReader(rosbag_path)
        duration = reader.get_duration()

        assert isinstance(duration, float)
        assert duration > 0.0

    def test_iterate_messages_by_topic(self, rosbag_path: Path) -> None:
        """Test iterating over messages from a specific topic."""
        from scripts.rosbag_reader import RosbagReader

        reader = RosbagReader(rosbag_path)
        topics = reader.get_available_topics()

        # Find a topic with image data
        depth_topic = next((t for t in topics if "Depth" in t and "image/data" in t), None)
        assert depth_topic is not None, "Depth image topic should exist"

        messages = list(reader.read_messages(depth_topic))

        assert len(messages) > 0
        # Each message should have timestamp, data, msgtype, and connection
        for msg_data in messages:
            assert "timestamp" in msg_data
            assert "data" in msg_data
            assert "msgtype" in msg_data
            assert "connection" in msg_data
            assert isinstance(msg_data["timestamp"], int)  # nanoseconds
            assert isinstance(msg_data["data"], bytes)  # raw data

    def test_invalid_bag_path(self) -> None:
        """Test that invalid path raises appropriate error."""
        from scripts.rosbag_reader import RosbagReader

        invalid_path = Path("/nonexistent/bag/file.bag")

        with pytest.raises((FileNotFoundError, ValueError)):
            reader = RosbagReader(invalid_path)
            # Attempting to read should fail
            list(reader.read_messages("any_topic"))

    def test_context_manager_support(self, rosbag_path: Path) -> None:
        """Test that RosbagReader works as a context manager."""
        from scripts.rosbag_reader import RosbagReader

        with RosbagReader(rosbag_path) as reader:
            topics = reader.get_available_topics()
            assert len(topics) > 0

    def test_filter_topics_by_pattern(self, rosbag_path: Path) -> None:
        """Test filtering topics by pattern (e.g., all image topics)."""
        from scripts.rosbag_reader import RosbagReader

        reader = RosbagReader(rosbag_path)
        image_topics = reader.filter_topics("image/data")

        assert isinstance(image_topics, list)
        assert all("image/data" in topic for topic in image_topics)

    def test_get_message_count_for_topic(self, rosbag_path: Path) -> None:
        """Test getting message count for a specific topic."""
        from scripts.rosbag_reader import RosbagReader

        reader = RosbagReader(rosbag_path)
        topics = reader.get_available_topics()

        if topics:
            first_topic = topics[0]
            count = reader.get_message_count(first_topic)

            assert isinstance(count, int)
            assert count >= 0
