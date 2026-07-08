"""RealSense data extraction from ROS messages.

This module provides functionality to extract and process RealSense sensor data
(RGB, Depth, IR, IMU) from deserialized ROS messages. Follows the Single
Responsibility Principle (SRP) by focusing on data extraction and transformation.
"""

from typing import Any

import numpy as np
from rosbags.typesys import Stores, get_typestore

from scripts.rosbag_deserializer import deserialize_ros1_lenient
from scripts.timestamp_handler import ros_timestamp_to_datetime


class DataExtractor:
    """Extractor for RealSense sensor data from ROS messages.

    This class provides methods to extract and process various types of sensor
    data from ROSbag messages, including images (RGB, Depth, IR) and IMU data.

    Example:
        >>> extractor = DataExtractor()
        >>> image_data = extractor.extract_image(rawdata, msgtype)
        >>> imu_data = extractor.extract_imu(rawdata, msgtype)
    """

    def __init__(self) -> None:
        """Initialize the data extractor with ROS1 typestore."""
        self.typestore = get_typestore(Stores.ROS1_NOETIC)

    def extract_image(
        self,
        rawdata: bytes,
        msgtype: str,
        timestamp_ns: int | None = None,
    ) -> dict[str, Any]:
        """Extract image data from sensor_msgs/Image message.

        Args:
            rawdata: Raw message data in CDR format
            msgtype: ROS message type name
            timestamp_ns: Optional timestamp in nanoseconds

        Returns:
            Dictionary containing:
            - timestamp: datetime or None
            - rawdata: original raw data (bytes)
            - msgtype: message type

        Raises:
            ValueError: If message type is not sensor_msgs/Image
        """
        if "Image" not in msgtype:
            raise ValueError(f"Expected Image message type, got {msgtype}")

        msg = deserialize_ros1_lenient(self.typestore, rawdata, msgtype)

        result: dict[str, Any] = {
            "rawdata": rawdata,
            "msgtype": msgtype,
            "width": int(msg.width),
            "height": int(msg.height),
            "encoding": str(msg.encoding),
        }

        # Add timestamp if provided
        if timestamp_ns is not None:
            result["timestamp"] = ros_timestamp_to_datetime(timestamp_ns)
        else:
            result["timestamp"] = None

        result["data"] = self._image_array(msg)

        return result

    def extract_imu(
        self,
        rawdata: bytes,
        msgtype: str,
        timestamp_ns: int | None = None,
    ) -> dict[str, Any]:
        """Extract IMU data from sensor_msgs/Imu message.

        Args:
            rawdata: Raw message data in CDR format
            msgtype: ROS message type name
            timestamp_ns: Optional timestamp in nanoseconds

        Returns:
            Dictionary containing:
            - timestamp: datetime or None
            - angular_velocity: dict with x, y, z components
            - linear_acceleration: dict with x, y, z components
            - rawdata: original raw data (bytes)

        Raises:
            ValueError: If message type is not sensor_msgs/Imu
        """
        if "Imu" not in msgtype:
            raise ValueError(f"Expected Imu message type, got {msgtype}")

        msg = deserialize_ros1_lenient(self.typestore, rawdata, msgtype)

        result: dict[str, Any] = {
            "angular_velocity": {
                "x": float(msg.angular_velocity.x),
                "y": float(msg.angular_velocity.y),
                "z": float(msg.angular_velocity.z),
            },
            "linear_acceleration": {
                "x": float(msg.linear_acceleration.x),
                "y": float(msg.linear_acceleration.y),
                "z": float(msg.linear_acceleration.z),
            },
            "rawdata": rawdata,
            "msgtype": msgtype,
        }

        # Add timestamp if provided
        if timestamp_ns is not None:
            result["timestamp"] = ros_timestamp_to_datetime(timestamp_ns)
        else:
            result["timestamp"] = None

        return result

    @staticmethod
    def _image_array(msg: Any) -> np.ndarray[Any, Any]:
        data = np.asarray(msg.data, dtype=np.uint8)
        height = int(msg.height)
        width = int(msg.width)
        encoding = str(msg.encoding).lower()
        step = int(msg.step)

        if encoding in {"16uc1", "mono16", "z16"}:
            dtype = ">u2" if int(msg.is_bigendian) else "<u2"
            row_bytes = width * np.dtype(dtype).itemsize
            rows = np.frombuffer(data.tobytes(), dtype=np.uint8).reshape(height, step)
            values = np.frombuffer(rows[:, :row_bytes].tobytes(), dtype=dtype)
            return values.astype(np.uint16, copy=False).reshape(height, width)

        if encoding in {"rgb8", "bgr8"}:
            channels = 3
        elif encoding in {"rgba8", "bgra8"}:
            channels = 4
        elif encoding in {"mono8", "8uc1"}:
            channels = 1
        else:
            channels = max(1, step // width) if width else 1

        row_bytes = width * channels
        rows = data.reshape(height, step)
        image = rows[:, :row_bytes].reshape(height, width, channels)
        if channels == 1:
            return image[:, :, 0]
        return image
