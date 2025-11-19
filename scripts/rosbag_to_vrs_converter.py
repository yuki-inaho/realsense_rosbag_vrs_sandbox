"""
ROSbag to VRS Converter

Converts RealSense D435i ROSbag files to VRS format.
Phase 4A implementation: Color + Depth (必須)
"""
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ROSbag reader (support both ROS1 and ROS2 via AnyReader)
try:
    from rosbags.highlevel import AnyReader  # type: ignore
except ImportError:
    raise ImportError("rosbags library is required. Install with: uv add rosbags")

# VRS writer
from scripts.vrs_writer import VRSWriter


@dataclass
class StreamConfig:
    """VRS stream configuration"""
    stream_id: int
    stream_type: str  # "color", "depth", "imu_accel", "imu_gyro"
    recordable_type_id: str  # "ForwardCamera", "MotionSensor"
    flavor: str


@dataclass
class ConverterConfig:
    """Converter configuration"""
    topic_mapping: dict[str, StreamConfig]
    phase: str  # "4A", "4B", "4C"
    compression: str = "lz4"
    verbose: bool = False


@dataclass
class ConversionResult:
    """Conversion result statistics"""
    input_bag_size: int  # bytes
    output_vrs_size: int  # bytes
    compression_ratio: float
    total_messages: int
    messages_per_stream: dict[int, int] = field(default_factory=dict)
    duration_sec: float = 0.0
    conversion_time_sec: float = 0.0


class RosbagToVRSConverter:
    """
    ROSbag to VRS converter (Phase 4A: Color + Depth)

    DRY/KISS/SOLID principles:
    - Single Responsibility: Only handles ROSbag -> VRS conversion
    - Open/Closed: New streams can be added via StreamConfig without modifying core logic
    - Dependency Inversion: Uses abstract VRSWriter interface
    """

    def __init__(self, rosbag_path: Path, vrs_path: Path, config: ConverterConfig):
        """
        Initialize converter

        Args:
            rosbag_path: Input ROSbag file path
            vrs_path: Output VRS file path
            config: Converter configuration
        """
        self.rosbag_path = Path(rosbag_path)
        self.vrs_path = Path(vrs_path)
        self.config = config

        # Statistics
        self._stats: dict[str, Any] = {
            "total_messages": 0,
            "messages_per_stream": {},
            "camera_info_cache": {}  # Cache CameraInfo messages
        }

    def convert(self) -> ConversionResult:
        """
        Execute conversion

        Returns:
            ConversionResult with statistics

        Raises:
            FileNotFoundError: ROSbag file not found
            OSError: Cannot create output VRS file
            ValueError: Invalid configuration or unsupported message type
        """
        # Validate input file exists
        if not self.rosbag_path.exists():
            raise FileNotFoundError(f"ROSbag file not found: {self.rosbag_path}")

        start_time = time.time()

        if self.config.verbose:
            print(f"Converting {self.rosbag_path} -> {self.vrs_path}")
            print(f"Phase: {self.config.phase}, Compression: {self.config.compression}")

        # Get input file size
        input_bag_size = self.rosbag_path.stat().st_size

        # Detect ROSbag format (ROS1 or ROS2)
        reader = self._open_rosbag()

        # Create VRS writer
        with VRSWriter(str(self.vrs_path)) as writer:
            # Create streams
            self._create_streams(writer)

            # Write configuration records (requires CameraInfo from bag)
            self._cache_camera_info(reader)
            self._write_configurations(writer)

            # Process messages in temporal order
            self._process_messages(reader, writer)

        # Calculate statistics
        output_vrs_size = self.vrs_path.stat().st_size
        conversion_time = time.time() - start_time

        # Extract bag duration (first to last message timestamp)
        duration_sec = self._calculate_bag_duration(reader)

        result = ConversionResult(
            input_bag_size=input_bag_size,
            output_vrs_size=output_vrs_size,
            compression_ratio=output_vrs_size / input_bag_size if input_bag_size > 0 else 0.0,
            total_messages=self._stats["total_messages"],
            messages_per_stream=self._stats["messages_per_stream"].copy(),
            duration_sec=duration_sec,
            conversion_time_sec=conversion_time
        )

        if self.config.verbose:
            print(f"Conversion complete in {conversion_time:.2f}s")
            print(f"Input: {input_bag_size/1024/1024:.2f} MB -> Output: {output_vrs_size/1024/1024:.2f} MB")
            print(f"Compression ratio: {result.compression_ratio:.2%}")
            print(f"Total messages: {result.total_messages}")
            print(f"Messages per stream: {result.messages_per_stream}")

        return result

    def _open_rosbag(self) -> Any:  # Returns AnyReader
        """Open ROSbag with auto-detection of format (ROS1 or ROS2)"""
        # AnyReader automatically detects ROSbag1 or ROSbag2 format
        try:
            return AnyReader([self.rosbag_path])
        except Exception as e:
            raise ValueError(f"Cannot open ROSbag: {e}") from e

    def _create_streams(self, writer: VRSWriter) -> None:
        """Create VRS streams based on topic mapping"""
        for topic, stream_config in self.config.topic_mapping.items():
            # VRSWriter.add_stream() accepts (stream_id, stream_name)
            # stream_name is automatically encoded with |id:stream_id format
            writer.add_stream(
                stream_config.stream_id,
                stream_config.flavor
            )

            # Initialize message counter
            self._stats["messages_per_stream"][stream_config.stream_id] = 0

            if self.config.verbose:
                print(f"Created stream {stream_config.stream_id}: {stream_config.flavor}")

    def _cache_camera_info(self, reader: Any) -> None:
        """
        Cache CameraInfo messages for Configuration records

        CameraInfo topics:
        - /device_0/sensor_1/Color_0/info/camera_info (for Color stream)
        - /device_0/sensor_0/Depth_0/info/camera_info (for Depth stream)
        """
        camera_info_topics = [
            "/device_0/sensor_1/Color_0/info/camera_info",
            "/device_0/sensor_0/Depth_0/info/camera_info"
        ]

        with reader:
            connections = [x for x in reader.connections if x.topic in camera_info_topics]

            for connection, timestamp, rawdata in reader.messages(connections=connections):
                # Deserialize message
                msg = reader.deserialize(rawdata, connection.msgtype)

                # Cache by topic
                self._stats["camera_info_cache"][connection.topic] = msg

                if self.config.verbose:
                    print(f"Cached CameraInfo from {connection.topic}")

                # Stop after getting one message per topic
                if len(self._stats["camera_info_cache"]) >= len(camera_info_topics):
                    break

    def _write_configurations(self, writer: VRSWriter) -> None:
        """Write Configuration records for each stream"""
        for topic, stream_config in self.config.topic_mapping.items():
            if stream_config.stream_type == "color":
                self._write_color_configuration(writer, stream_config, topic)
            elif stream_config.stream_type == "depth":
                self._write_depth_configuration(writer, stream_config, topic)
            elif stream_config.stream_type == "imu_accel":
                self._write_imu_accel_configuration(writer, stream_config, topic)
            elif stream_config.stream_type == "imu_gyro":
                self._write_imu_gyro_configuration(writer, stream_config, topic)

    def _write_color_configuration(self, writer: VRSWriter, stream_config: StreamConfig, topic: str) -> None:
        """Write Color stream Configuration record"""
        camera_info_topic = "/device_0/sensor_1/Color_0/info/camera_info"
        camera_info = self._stats["camera_info_cache"].get(camera_info_topic)

        if camera_info is None:
            raise ValueError(f"CameraInfo not found for {camera_info_topic}")

        config_data = {
            "width": int(camera_info.width),
            "height": int(camera_info.height),
            "encoding": "rgb8",  # Default, will be overridden by actual message encoding
            "camera_k": list(camera_info.K),  # 9 elements
            "camera_d": list(camera_info.D),  # 5 elements (distortion coefficients)
            "distortion_model": camera_info.distortion_model,
            "frame_id": camera_info.header.frame_id  # Store frame_id in configuration
        }

        writer.write_configuration(stream_config.stream_id, config_data)

        if self.config.verbose:
            print(f"Wrote Configuration for stream {stream_config.stream_id} (Color): {camera_info.width}x{camera_info.height}")

    def _write_depth_configuration(self, writer: VRSWriter, stream_config: StreamConfig, topic: str) -> None:
        """Write Depth stream Configuration record"""
        camera_info_topic = "/device_0/sensor_0/Depth_0/info/camera_info"
        camera_info = self._stats["camera_info_cache"].get(camera_info_topic)

        if camera_info is None:
            raise ValueError(f"CameraInfo not found for {camera_info_topic}")

        config_data = {
            "width": int(camera_info.width),
            "height": int(camera_info.height),
            "encoding": "16UC1",  # Depth encoding
            "camera_k": list(camera_info.K),
            "camera_d": list(camera_info.D),
            "distortion_model": camera_info.distortion_model,
            "depth_scale": 0.001,  # mm -> meters
            "frame_id": camera_info.header.frame_id  # Store frame_id in configuration
        }

        writer.write_configuration(stream_config.stream_id, config_data)

        if self.config.verbose:
            print(f"Wrote Configuration for stream {stream_config.stream_id} (Depth): {camera_info.width}x{camera_info.height}")

    def _write_imu_accel_configuration(self, writer: VRSWriter, stream_config: StreamConfig, topic: str) -> None:
        """Write IMU Accelerometer Configuration record"""
        config_data = {
            "sensor_type": "accelerometer",
            "frame_id": "0",
            "unit": "m/s^2",
            "sample_rate": 44.0,  # Estimated from ROSbag analysis
            "axes": ["x", "y", "z"],
            "range": None,  # Not specified in ROSbag
            "noise_variances": [0.0, 0.0, 0.0],  # From IMU intrinsic (all zeros)
            "bias_variances": [0.0, 0.0, 0.0]
        }

        writer.write_configuration(stream_config.stream_id, config_data)

        if self.config.verbose:
            print(f"Wrote Configuration for stream {stream_config.stream_id} (Accel): {config_data['sample_rate']} Hz")

    def _write_imu_gyro_configuration(self, writer: VRSWriter, stream_config: StreamConfig, topic: str) -> None:
        """Write IMU Gyroscope Configuration record"""
        config_data = {
            "sensor_type": "gyroscope",
            "frame_id": "0",
            "unit": "rad/s",
            "sample_rate": 55.0,  # Estimated from ROSbag analysis
            "axes": ["x", "y", "z"],
            "range": None,  # Not specified in ROSbag
            "noise_variances": [0.0, 0.0, 0.0],  # From IMU intrinsic (all zeros)
            "bias_variances": [0.0, 0.0, 0.0]
        }

        writer.write_configuration(stream_config.stream_id, config_data)

        if self.config.verbose:
            print(f"Wrote Configuration for stream {stream_config.stream_id} (Gyro): {config_data['sample_rate']} Hz")

    def _process_messages(self, reader: Any, writer: VRSWriter) -> None:
        """Process all messages in temporal order"""
        target_topics = list(self.config.topic_mapping.keys())

        with reader:
            connections = [x for x in reader.connections if x.topic in target_topics]

            if not connections:
                raise ValueError(f"No messages found for topics: {target_topics}")

            for connection, timestamp, rawdata in reader.messages(connections=connections):
                # Get stream config
                stream_config = self.config.topic_mapping.get(connection.topic)
                if stream_config is None:
                    continue  # Skip topics not in mapping

                # Deserialize message
                msg = reader.deserialize(rawdata, connection.msgtype)

                # Convert and write based on stream type
                if stream_config.stream_type == "color":
                    self._process_color_message(writer, stream_config, msg, timestamp)
                elif stream_config.stream_type == "depth":
                    self._process_depth_message(writer, stream_config, msg, timestamp)
                elif stream_config.stream_type == "imu_accel":
                    self._process_imu_accel_message(writer, stream_config, msg, timestamp)
                elif stream_config.stream_type == "imu_gyro":
                    self._process_imu_gyro_message(writer, stream_config, msg, timestamp)

                # Update statistics
                self._stats["total_messages"] += 1
                self._stats["messages_per_stream"][stream_config.stream_id] += 1

    def _process_color_message(self, writer: VRSWriter, stream_config: StreamConfig, msg: Any, timestamp: int) -> None:
        """Process Color Image message"""
        # Convert timestamp (nanoseconds -> seconds)
        timestamp_sec = timestamp / 1e9

        # Extract image data
        image_data = bytes(msg.data)

        # Write Data record (timestamp + Image bytes)
        # Note: frame_id and encoding are stored in Configuration record
        writer.write_data(stream_config.stream_id, timestamp_sec, image_data)

    def _process_depth_message(self, writer: VRSWriter, stream_config: StreamConfig, msg: Any, timestamp: int) -> None:
        """Process Depth Image message"""
        # Convert timestamp (nanoseconds -> seconds)
        timestamp_sec = timestamp / 1e9

        # Extract depth data
        depth_data = bytes(msg.data)

        # Write Data record (timestamp + Depth bytes)
        # Note: frame_id and encoding are stored in Configuration record
        writer.write_data(stream_config.stream_id, timestamp_sec, depth_data)

    def _process_imu_accel_message(self, writer: VRSWriter, stream_config: StreamConfig, msg: Any, timestamp: int) -> None:
        """Process IMU Accelerometer message (Phase 4B)"""
        import struct

        # Convert timestamp (nanoseconds -> seconds)
        timestamp_sec = timestamp / 1e9

        # Extract linear acceleration (x, y, z) from sensor_msgs/Imu
        # Pack as 3 doubles (24 bytes)
        imu_data = struct.pack(
            '<ddd',
            msg.linear_acceleration.x,
            msg.linear_acceleration.y,
            msg.linear_acceleration.z
        )

        # Write Data record (timestamp + 24 bytes)
        writer.write_data(stream_config.stream_id, timestamp_sec, imu_data)

    def _process_imu_gyro_message(self, writer: VRSWriter, stream_config: StreamConfig, msg: Any, timestamp: int) -> None:
        """Process IMU Gyroscope message (Phase 4B)"""
        import struct

        # Convert timestamp (nanoseconds -> seconds)
        timestamp_sec = timestamp / 1e9

        # Extract angular velocity (x, y, z) from sensor_msgs/Imu
        # Pack as 3 doubles (24 bytes)
        imu_data = struct.pack(
            '<ddd',
            msg.angular_velocity.x,
            msg.angular_velocity.y,
            msg.angular_velocity.z
        )

        # Write Data record (timestamp + 24 bytes)
        writer.write_data(stream_config.stream_id, timestamp_sec, imu_data)

    def _calculate_bag_duration(self, reader: Any) -> float:
        """Calculate bag duration (first to last message timestamp)"""
        min_ts = float('inf')
        max_ts = float('-inf')

        try:
            with reader:
                for connection, timestamp, rawdata in reader.messages():
                    min_ts = min(min_ts, timestamp)
                    max_ts = max(max_ts, timestamp)

                    # Early exit after 1000 messages for performance
                    # (assumes messages are somewhat evenly distributed)
                    if max_ts - min_ts > 1e9:  # At least 1 second
                        break
        except Exception:
            # If we can't read messages, return 0
            return 0.0

        # Convert nanoseconds -> seconds
        duration_sec = (max_ts - min_ts) / 1e9
        return max(0.0, duration_sec)


# RGB-D stream mapping (Color + Depth)
RGBD_STREAMS = {
    "/device_0/sensor_1/Color_0/image/data": StreamConfig(
        stream_id=1001,
        stream_type="color",
        recordable_type_id="ForwardCamera",
        flavor="RealSense_D435i_Color|id:1001"
    ),
    "/device_0/sensor_0/Depth_0/image/data": StreamConfig(
        stream_id=1002,
        stream_type="depth",
        recordable_type_id="ForwardCamera",
        flavor="RealSense_D435i_Depth|id:1002"
    ),
}


# RGB-D + IMU stream mapping
RGBD_IMU_STREAMS = {
    **RGBD_STREAMS,
    "/device_0/sensor_2/Accel_0/imu/data": StreamConfig(
        stream_id=1003,
        stream_type="imu_accel",
        recordable_type_id="MotionSensor",
        flavor="RealSense_D435i_Accel|id:1003"
    ),
    "/device_0/sensor_2/Gyro_0/imu/data": StreamConfig(
        stream_id=1004,
        stream_type="imu_gyro",
        recordable_type_id="MotionSensor",
        flavor="RealSense_D435i_Gyro|id:1004"
    ),
}


def create_rgbd_config(compression: str = "lz4", verbose: bool = False) -> ConverterConfig:
    """Create RGB-D converter configuration (Color + Depth only)"""
    return ConverterConfig(
        topic_mapping=RGBD_STREAMS,
        phase="rgbd",
        compression=compression,
        verbose=verbose
    )


def create_rgbd_imu_config(compression: str = "lz4", verbose: bool = False) -> ConverterConfig:
    """Create RGB-D + IMU converter configuration"""
    return ConverterConfig(
        topic_mapping=RGBD_IMU_STREAMS,
        phase="rgbd_imu",
        compression=compression,
        verbose=verbose
    )
