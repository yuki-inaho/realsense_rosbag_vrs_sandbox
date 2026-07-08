"""Tests for RealSense data extraction functionality."""

from pathlib import Path

import numpy as np
import pytest


class TestDataExtractor:
    """Test cases for extracting RealSense data from ROSbag messages."""

    def test_extract_image_data(self, rosbag_path: Path) -> None:
        """Test extracting image data from sensor_msgs/Image message."""
        from scripts.data_extractor import DataExtractor
        from scripts.rosbag_reader import RosbagReader

        extractor = DataExtractor()
        reader = RosbagReader(rosbag_path)

        # Find an image topic
        topics = reader.get_available_topics()
        image_topic = next((t for t in topics if "image/data" in t and "Depth" in t), None)
        assert image_topic is not None

        # Get first message
        messages = list(reader.read_messages(image_topic))
        assert len(messages) > 0

        msg = messages[0]
        image_data = extractor.extract_image(msg["data"], msg["msgtype"])

        assert image_data is not None
        assert "timestamp" in image_data
        assert "width" in image_data
        assert "height" in image_data
        assert "encoding" in image_data
        assert "data" in image_data
        assert isinstance(image_data["data"], np.ndarray)

    def test_extract_depth_image(self, rosbag_path: Path) -> None:
        """Test extracting depth image with proper uint16 encoding."""
        from scripts.data_extractor import DataExtractor
        from scripts.rosbag_reader import RosbagReader

        extractor = DataExtractor()
        reader = RosbagReader(rosbag_path)

        topics = reader.get_available_topics()
        depth_topic = next((t for t in topics if "Depth" in t and "image/data" in t), None)
        assert depth_topic is not None

        messages = list(reader.read_messages(depth_topic))
        msg = messages[0]
        image_data = extractor.extract_image(msg["data"], msg["msgtype"])

        # Depth images are typically uint16
        assert image_data["data"].dtype in [np.uint16, np.float32]
        assert image_data["width"] > 0
        assert image_data["height"] > 0

    def test_extract_color_image(self, rosbag_path: Path) -> None:
        """Test extracting color/RGB image."""
        from scripts.data_extractor import DataExtractor
        from scripts.rosbag_reader import RosbagReader

        extractor = DataExtractor()
        reader = RosbagReader(rosbag_path)

        topics = reader.get_available_topics()
        color_topic = next((t for t in topics if "Color" in t and "image/data" in t), None)
        assert color_topic is not None

        messages = list(reader.read_messages(color_topic))
        msg = messages[0]
        image_data = extractor.extract_image(msg["data"], msg["msgtype"])

        # Color images typically have 3 channels (RGB) or 4 (RGBA)
        assert len(image_data["data"].shape) >= 2
        if len(image_data["data"].shape) == 3:
            assert image_data["data"].shape[2] in [3, 4]

    def test_extract_imu_data(self, rosbag_path: Path) -> None:
        """Test extracting IMU data (accelerometer and gyroscope)."""
        from scripts.data_extractor import DataExtractor
        from scripts.rosbag_reader import RosbagReader

        extractor = DataExtractor()
        reader = RosbagReader(rosbag_path)

        topics = reader.get_available_topics()
        imu_topic = next((t for t in topics if "imu/data" in t), None)
        if imu_topic is None:
            pytest.skip("ROSbag does not contain IMU topics")

        messages = list(reader.read_messages(imu_topic))
        assert len(messages) > 0

        msg = messages[0]
        imu_data = extractor.extract_imu(msg["data"], msg["msgtype"])

        assert imu_data is not None
        assert "timestamp" in imu_data
        assert "angular_velocity" in imu_data
        assert "linear_acceleration" in imu_data

        # Check that angular velocity has x, y, z components
        assert "x" in imu_data["angular_velocity"]
        assert "y" in imu_data["angular_velocity"]
        assert "z" in imu_data["angular_velocity"]

        # Check that linear acceleration has x, y, z components
        assert "x" in imu_data["linear_acceleration"]
        assert "y" in imu_data["linear_acceleration"]
        assert "z" in imu_data["linear_acceleration"]

    def test_extract_accel_data(self, rosbag_path: Path) -> None:
        """Test extracting accelerometer-specific IMU data."""
        from scripts.data_extractor import DataExtractor
        from scripts.rosbag_reader import RosbagReader

        extractor = DataExtractor()
        reader = RosbagReader(rosbag_path)

        topics = reader.get_available_topics()
        accel_topic = next((t for t in topics if "Accel" in t and "imu/data" in t), None)
        if accel_topic is None:
            pytest.skip("ROSbag does not contain accelerometer IMU topics")

        messages = list(reader.read_messages(accel_topic))
        msg = messages[0]
        imu_data = extractor.extract_imu(msg["data"], msg["msgtype"])

        # Accelerometer data should have linear acceleration
        assert imu_data["linear_acceleration"]["x"] is not None
        assert isinstance(imu_data["linear_acceleration"]["x"], float)

    def test_extract_gyro_data(self, rosbag_path: Path) -> None:
        """Test extracting gyroscope-specific IMU data."""
        from scripts.data_extractor import DataExtractor
        from scripts.rosbag_reader import RosbagReader

        extractor = DataExtractor()
        reader = RosbagReader(rosbag_path)

        topics = reader.get_available_topics()
        gyro_topic = next((t for t in topics if "Gyro" in t and "imu/data" in t), None)
        if gyro_topic is None:
            pytest.skip("ROSbag does not contain gyroscope IMU topics")

        messages = list(reader.read_messages(gyro_topic))
        msg = messages[0]
        imu_data = extractor.extract_imu(msg["data"], msg["msgtype"])

        # Gyroscope data should have angular velocity
        assert imu_data["angular_velocity"]["x"] is not None
        assert isinstance(imu_data["angular_velocity"]["x"], float)

    def test_extract_with_timestamp_conversion(self, rosbag_path: Path) -> None:
        """Test that extracted data includes properly converted timestamps."""
        from datetime import datetime

        from scripts.data_extractor import DataExtractor
        from scripts.rosbag_reader import RosbagReader

        extractor = DataExtractor()
        reader = RosbagReader(rosbag_path)

        topics = reader.get_available_topics()
        any_topic = next((t for t in topics if "image/data" in t), None)
        assert any_topic is not None

        messages = list(reader.read_messages(any_topic))
        msg = messages[0]

        # Extract with message timestamp
        extracted = extractor.extract_image(
            msg["data"], msg["msgtype"], timestamp_ns=msg["timestamp"]
        )

        assert "timestamp" in extracted
        # Timestamp should be a datetime object or ISO string
        assert isinstance(extracted["timestamp"], (datetime, str, int, float))

    def test_invalid_message_type(self) -> None:
        """Test handling of invalid message types."""
        from scripts.data_extractor import DataExtractor

        extractor = DataExtractor()
        invalid_data = b"invalid data"

        with pytest.raises((ValueError, TypeError, Exception)):
            extractor.extract_image(invalid_data, "invalid/MessageType")
