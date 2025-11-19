"""
ROSbag to VRS Converter

Converts RealSense D435i ROSbag files to VRS format.
Color + Depth (必須)
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
    ROSbag to VRS converter (Color + Depth)

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
            "camera_info_cache": {},  # Cache CameraInfo messages
            "transform_cache": {},  # Cache Transform messages
            "stream_info_cache": {},  # Cache StreamInfo messages
            "device_info_cache": {},  # Cache Device Info KeyValue pairs
            "sensor_info_cache": {},  # Cache Sensor Info messages
            "options_cache": {}  # Cache Options messages
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

            # Write configuration records (requires CameraInfo, Transform, and Info data from bag)
            self._cache_camera_info(reader)
            self._cache_transforms(reader)
            self._cache_stream_info(reader)
            self._cache_device_info(reader)
            self._cache_sensor_info(reader)
            self._cache_options(reader)
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

    def _cache_transforms(self, reader: Any) -> None:
        """
        Cache Transform messages for Configuration records

        Transform topics:
        - /device_0/sensor_0/Depth_0/tf/0 (Depth Extrinsic)
        - /device_0/sensor_1/Color_0/tf/0 (Color Extrinsic)
        """
        transform_topics = [
            "/device_0/sensor_0/Depth_0/tf/0",
            "/device_0/sensor_1/Color_0/tf/0"
        ]

        with reader:
            connections = [x for x in reader.connections if x.topic in transform_topics]

            # Transform topics may not exist in all bags (optional)
            if not connections:
                if self.config.verbose:
                    print("No Transform topics found in ROSbag (skipping)")
                return

            for connection, timestamp, rawdata in reader.messages(connections=connections):
                # Deserialize message
                msg = reader.deserialize(rawdata, connection.msgtype)

                # Cache by topic
                self._stats["transform_cache"][connection.topic] = msg

                if self.config.verbose:
                    print(f"Cached Transform from {connection.topic}")

                # Stop after getting one message per topic (Transforms are static)
                if len(self._stats["transform_cache"]) >= len(transform_topics):
                    break

    def _cache_stream_info(self, reader: Any) -> None:
        """
        Cache StreamInfo messages for Configuration records

        StreamInfo topics:
        - /device_0/sensor_0/Depth_0/info
        - /device_0/sensor_1/Color_0/info
        - /device_0/sensor_2/Accel_0/info
        - /device_0/sensor_2/Gyro_0/info
        """
        stream_info_topics = [
            "/device_0/sensor_0/Depth_0/info",
            "/device_0/sensor_1/Color_0/info",
            "/device_0/sensor_2/Accel_0/info",
            "/device_0/sensor_2/Gyro_0/info"
        ]

        with reader:
            connections = [x for x in reader.connections if x.topic in stream_info_topics]

            if not connections:
                if self.config.verbose:
                    print("No StreamInfo topics found in ROSbag (skipping)")
                return

            for connection, timestamp, rawdata in reader.messages(connections=connections):
                msg = reader.deserialize(rawdata, connection.msgtype)
                self._stats["stream_info_cache"][connection.topic] = msg

                if self.config.verbose:
                    print(f"Cached StreamInfo from {connection.topic}: fps={msg.fps}, encoding={msg.encoding}")

    def _cache_device_info(self, reader: Any) -> None:
        """
        Cache Device Info messages

        Device Info topics:
        - /device_0/info (multiple KeyValue pairs)
        """
        device_info_topic = "/device_0/info"
        device_info_dict = {}

        with reader:
            connections = [x for x in reader.connections if x.topic == device_info_topic]

            if not connections:
                if self.config.verbose:
                    print("No Device Info topics found in ROSbag (skipping)")
                return

            for connection, timestamp, rawdata in reader.messages(connections=connections):
                msg = reader.deserialize(rawdata, connection.msgtype)
                device_info_dict[msg.key] = msg.value

            self._stats["device_info_cache"] = device_info_dict

            if self.config.verbose:
                print(f"Cached Device Info ({len(device_info_dict)} key-value pairs)")

    def _cache_sensor_info(self, reader: Any) -> None:
        """
        Cache Sensor Info messages

        Sensor Info topics:
        - /device_0/sensor_0/info
        - /device_0/sensor_1/info
        - /device_0/sensor_2/info
        """
        sensor_info_topics = [
            "/device_0/sensor_0/info",
            "/device_0/sensor_1/info",
            "/device_0/sensor_2/info"
        ]

        with reader:
            connections = [x for x in reader.connections if x.topic in sensor_info_topics]

            if not connections:
                if self.config.verbose:
                    print("No Sensor Info topics found in ROSbag (skipping)")
                return

            for connection, timestamp, rawdata in reader.messages(connections=connections):
                msg = reader.deserialize(rawdata, connection.msgtype)
                self._stats["sensor_info_cache"][connection.topic] = msg

                if self.config.verbose:
                    print(f"Cached Sensor Info from {connection.topic}: {msg.value}")

    def _cache_options(self, reader: Any) -> None:
        """
        Cache Options messages for Configuration record

        Options topics:
        - /device_0/sensor_*/option/*/value (25 topics)
        - /device_0/sensor_*/option/*/description (25 topics)
        """
        options_dict = {}  # {option_name: {sensor, value, description}}

        with reader:
            # Find all option topics
            option_connections = [
                c for c in reader.connections
                if '/option/' in c.topic
            ]

            if not option_connections:
                if self.config.verbose:
                    print("No Options topics found in ROSbag (skipping)")
                return

            for connection, timestamp, rawdata in reader.messages(connections=option_connections):
                msg = reader.deserialize(rawdata, connection.msgtype)

                # Parse topic: /device_0/sensor_X/option/OPTION_NAME/TYPE
                parts = connection.topic.split('/')
                if len(parts) < 6:
                    continue  # Invalid topic format

                sensor_id = parts[2]  # sensor_0, sensor_1, sensor_2
                option_name = parts[4]  # Exposure, Gain, etc.
                option_type = parts[5]  # value or description

                # Initialize option entry if not exists
                if option_name not in options_dict:
                    options_dict[option_name] = {
                        'sensor': sensor_id,
                        'value': None,
                        'description': None
                    }

                # Store value or description
                if option_type == 'value':
                    options_dict[option_name]['value'] = float(msg.data)
                elif option_type == 'description':
                    options_dict[option_name]['description'] = str(msg.data)

            self._stats["options_cache"] = options_dict

            if self.config.verbose:
                print(f"Cached {len(options_dict)} Options")

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
            elif stream_config.stream_type == "transform_depth":
                self._write_transform_depth_configuration(writer, stream_config, topic)
            elif stream_config.stream_type == "transform_color":
                self._write_transform_color_configuration(writer, stream_config, topic)
            elif stream_config.stream_type == "device_info":
                self._write_device_info_configuration(writer, stream_config, topic)
            elif stream_config.stream_type == "sensor_info":
                self._write_sensor_info_configuration(writer, stream_config, topic)
            elif stream_config.stream_type == "options":
                self._write_options_configuration(writer, stream_config, topic)

    def _write_color_configuration(self, writer: VRSWriter, stream_config: StreamConfig, topic: str) -> None:
        """Write Color stream Configuration record"""
        camera_info_topic = "/device_0/sensor_1/Color_0/info/camera_info"
        camera_info = self._stats["camera_info_cache"].get(camera_info_topic)

        if camera_info is None:
            raise ValueError(f"CameraInfo not found for {camera_info_topic}")

        config_data = {
            "width": int(camera_info.width),
            "height": int(camera_info.height),
            "encoding": "rgb8",  # Default, will be overridden by StreamInfo
            "camera_k": list(camera_info.K),  # 9 elements
            "camera_d": list(camera_info.D),  # 5 elements (distortion coefficients)
            "distortion_model": camera_info.distortion_model,
            "frame_id": camera_info.header.frame_id  # Store frame_id in configuration
        }

        # Add StreamInfo if available
        stream_info_topic = "/device_0/sensor_1/Color_0/info"
        stream_info = self._stats["stream_info_cache"].get(stream_info_topic)

        if stream_info:
            config_data["fps"] = int(stream_info.fps)
            config_data["encoding"] = str(stream_info.encoding)  # Override with actual encoding
            config_data["is_recommended"] = bool(stream_info.is_recommended)

        writer.write_configuration(stream_config.stream_id, config_data)

        if self.config.verbose:
            fps_str = f", fps={config_data.get('fps', 'N/A')}" if "fps" in config_data else ""
            print(f"Wrote Configuration for stream {stream_config.stream_id} (Color): {camera_info.width}x{camera_info.height}{fps_str}")

    def _write_depth_configuration(self, writer: VRSWriter, stream_config: StreamConfig, topic: str) -> None:
        """Write Depth stream Configuration record"""
        camera_info_topic = "/device_0/sensor_0/Depth_0/info/camera_info"
        camera_info = self._stats["camera_info_cache"].get(camera_info_topic)

        if camera_info is None:
            raise ValueError(f"CameraInfo not found for {camera_info_topic}")

        config_data = {
            "width": int(camera_info.width),
            "height": int(camera_info.height),
            "encoding": "16UC1",  # Depth encoding, will be overridden by StreamInfo
            "camera_k": list(camera_info.K),
            "camera_d": list(camera_info.D),
            "distortion_model": camera_info.distortion_model,
            "depth_scale": 0.001,  # mm -> meters
            "frame_id": camera_info.header.frame_id  # Store frame_id in configuration
        }

        # Add StreamInfo if available
        stream_info_topic = "/device_0/sensor_0/Depth_0/info"
        stream_info = self._stats["stream_info_cache"].get(stream_info_topic)

        if stream_info:
            config_data["fps"] = int(stream_info.fps)
            config_data["encoding"] = str(stream_info.encoding)  # Override with actual encoding
            config_data["is_recommended"] = bool(stream_info.is_recommended)

        writer.write_configuration(stream_config.stream_id, config_data)

        if self.config.verbose:
            fps_str = f", fps={config_data.get('fps', 'N/A')}" if "fps" in config_data else ""
            print(f"Wrote Configuration for stream {stream_config.stream_id} (Depth): {camera_info.width}x{camera_info.height}{fps_str}")

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

        # Add StreamInfo if available
        stream_info_topic = "/device_0/sensor_2/Accel_0/info"
        stream_info = self._stats["stream_info_cache"].get(stream_info_topic)

        if stream_info:
            config_data["fps"] = int(stream_info.fps)
            config_data["encoding"] = str(stream_info.encoding)
            config_data["is_recommended"] = bool(stream_info.is_recommended)

        writer.write_configuration(stream_config.stream_id, config_data)

        if self.config.verbose:
            fps_str = f", fps={config_data.get('fps', 'N/A')}" if "fps" in config_data else ""
            print(f"Wrote Configuration for stream {stream_config.stream_id} (Accel): {config_data['sample_rate']} Hz{fps_str}")

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

        # Add StreamInfo if available
        stream_info_topic = "/device_0/sensor_2/Gyro_0/info"
        stream_info = self._stats["stream_info_cache"].get(stream_info_topic)

        if stream_info:
            config_data["fps"] = int(stream_info.fps)
            config_data["encoding"] = str(stream_info.encoding)
            config_data["is_recommended"] = bool(stream_info.is_recommended)

        writer.write_configuration(stream_config.stream_id, config_data)

        if self.config.verbose:
            fps_str = f", fps={config_data.get('fps', 'N/A')}" if "fps" in config_data else ""
            print(f"Wrote Configuration for stream {stream_config.stream_id} (Gyro): {config_data['sample_rate']} Hz{fps_str}")

    def _write_transform_depth_configuration(self, writer: VRSWriter, stream_config: StreamConfig, topic: str) -> None:
        """Write Depth Extrinsic Configuration record"""
        transform_msg = self._stats["transform_cache"].get(topic)

        if transform_msg is None:
            # Default to identity transform if not found
            config_data = {
                "transform_type": "static",
                "sensor_name": "Depth",
                "reference_frame": "device_0",
                "translation": {"x": 0.0, "y": 0.0, "z": 0.0, "unit": "meters"},
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0, "format": "quaternion"}
            }
            if self.config.verbose:
                print(f"Depth Transform not found, using identity transform (default)")
        else:
            config_data = {
                "transform_type": "static",
                "sensor_name": "Depth",
                "reference_frame": "device_0",
                "translation": {
                    "x": float(transform_msg.translation.x),
                    "y": float(transform_msg.translation.y),
                    "z": float(transform_msg.translation.z),
                    "unit": "meters"
                },
                "rotation": {
                    "x": float(transform_msg.rotation.x),
                    "y": float(transform_msg.rotation.y),
                    "z": float(transform_msg.rotation.z),
                    "w": float(transform_msg.rotation.w),
                    "format": "quaternion"
                }
            }

        writer.write_configuration(stream_config.stream_id, config_data)

        if self.config.verbose:
            print(f"Wrote Configuration for stream {stream_config.stream_id} (Depth Extrinsic): "
                  f"T=({config_data['translation']['x']:.6f}, {config_data['translation']['y']:.6f}, {config_data['translation']['z']:.6f})")

    def _write_transform_color_configuration(self, writer: VRSWriter, stream_config: StreamConfig, topic: str) -> None:
        """Write Color Extrinsic Configuration record"""
        transform_msg = self._stats["transform_cache"].get(topic)

        if transform_msg is None:
            # Raise error if Color transform is missing (should be present in D435i bags)
            raise ValueError(f"Transform message not found for topic: {topic}")

        config_data = {
            "transform_type": "static",
            "sensor_name": "Color",
            "reference_frame": "device_0",
            "translation": {
                "x": float(transform_msg.translation.x),
                "y": float(transform_msg.translation.y),
                "z": float(transform_msg.translation.z),
                "unit": "meters"
            },
            "rotation": {
                "x": float(transform_msg.rotation.x),
                "y": float(transform_msg.rotation.y),
                "z": float(transform_msg.rotation.z),
                "w": float(transform_msg.rotation.w),
                "format": "quaternion"
            }
        }

        writer.write_configuration(stream_config.stream_id, config_data)

        if self.config.verbose:
            print(f"Wrote Configuration for stream {stream_config.stream_id} (Color Extrinsic): "
                  f"T=({config_data['translation']['x']:.6f}, {config_data['translation']['y']:.6f}, {config_data['translation']['z']:.6f})")

    def _write_device_info_configuration(self, writer: VRSWriter, stream_config: StreamConfig, topic: str) -> None:
        """Write Device Info Configuration record"""
        device_info_dict = self._stats.get("device_info_cache", {})

        if not device_info_dict:
            if self.config.verbose:
                print(f"Device Info not found, skipping stream {stream_config.stream_id}")
            return

        # Build configuration from KeyValue pairs
        config_data = {
            "info_type": "device",
            "device_name": device_info_dict.get("Name", "Unknown"),
            "serial_number": device_info_dict.get("Serial Number", ""),
            "firmware_version": device_info_dict.get("Firmware Version", ""),
            "recommended_firmware_version": device_info_dict.get("Recommended Firmware Version", ""),
            "physical_port": device_info_dict.get("Physical Port", ""),
            "debug_op_code": device_info_dict.get("Debug Op Code", ""),
            "advanced_mode": device_info_dict.get("Advanced Mode", ""),
            "product_id": device_info_dict.get("Product Id", ""),
            "usb_type_descriptor": device_info_dict.get("Usb Type Descriptor", "")
        }

        writer.write_configuration(stream_config.stream_id, config_data)

        if self.config.verbose:
            print(f"Wrote Configuration for stream {stream_config.stream_id} (Device Info): {config_data['device_name']} (SN: {config_data['serial_number']})")

    def _write_sensor_info_configuration(self, writer: VRSWriter, stream_config: StreamConfig, topic: str) -> None:
        """Write Sensor Info Configuration record"""
        sensor_info_msg = self._stats["sensor_info_cache"].get(topic)

        if sensor_info_msg is None:
            if self.config.verbose:
                print(f"Sensor Info not found for {topic}, skipping stream {stream_config.stream_id}")
            return

        # Extract sensor_id from topic (e.g., "/device_0/sensor_0/info" -> "sensor_0")
        sensor_id = topic.split("/")[2] if len(topic.split("/")) > 2 else "unknown"

        # Determine associated streams based on sensor_id
        associated_streams = []
        if sensor_id == "sensor_0":
            associated_streams = [1002, 1005]  # Depth, Depth Extrinsic
        elif sensor_id == "sensor_1":
            associated_streams = [1001, 1006]  # Color, Color Extrinsic
        elif sensor_id == "sensor_2":
            associated_streams = [1003, 1004]  # Accel, Gyro

        config_data = {
            "info_type": "sensor",
            "sensor_id": sensor_id,
            "sensor_name": sensor_info_msg.value,
            "associated_streams": associated_streams
        }

        writer.write_configuration(stream_config.stream_id, config_data)

        if self.config.verbose:
            print(f"Wrote Configuration for stream {stream_config.stream_id} (Sensor Info): {config_data['sensor_name']} ({sensor_id})")

    def _write_options_configuration(self, writer: VRSWriter, stream_config: StreamConfig, topic: str) -> None:
        """Write Options Configuration record"""
        options_dict = self._stats.get("options_cache", {})

        if not options_dict:
            if self.config.verbose:
                print(f"No Options found in ROSbag, skipping stream {stream_config.stream_id}")
            return

        # Build options array
        options_array = []
        for name, data in sorted(options_dict.items()):
            options_array.append({
                "name": name,
                "sensor": data['sensor'],
                "value": data['value'],
                "description": data['description']
            })

        config_data = {
            "info_type": "options",
            "total_options": len(options_array),
            "options": options_array
        }

        writer.write_configuration(stream_config.stream_id, config_data)

        if self.config.verbose:
            print(f"Wrote Configuration for stream {stream_config.stream_id} (Options): {len(options_array)} options")

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
        """Process IMU Accelerometer message"""
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
        """Process IMU Gyroscope message"""
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


# RGB-D stream mapping (Color + Depth + Transform)
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
    "/device_0/sensor_0/Depth_0/tf/0": StreamConfig(
        stream_id=1005,
        stream_type="transform_depth",
        recordable_type_id="ForwardCamera",
        flavor="RealSense_D435i_Depth_Extrinsic|id:1005"
    ),
    "/device_0/sensor_1/Color_0/tf/0": StreamConfig(
        stream_id=1006,
        stream_type="transform_color",
        recordable_type_id="ForwardCamera",
        flavor="RealSense_D435i_Color_Extrinsic|id:1006"
    ),
}


# RGB-D + IMU stream mapping (Transform included via RGBD_STREAMS)
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
    "/device_0/info": StreamConfig(
        stream_id=2001,
        stream_type="device_info",
        recordable_type_id="ForwardCamera",
        flavor="RealSense_D435i_Device_Info|id:2001"
    ),
    "/device_0/sensor_0/info": StreamConfig(
        stream_id=2002,
        stream_type="sensor_info",
        recordable_type_id="ForwardCamera",
        flavor="RealSense_D435i_Sensor0_Info|id:2002"
    ),
    "/device_0/sensor_1/info": StreamConfig(
        stream_id=2003,
        stream_type="sensor_info",
        recordable_type_id="ForwardCamera",
        flavor="RealSense_D435i_Sensor1_Info|id:2003"
    ),
    "/device_0/sensor_2/info": StreamConfig(
        stream_id=2004,
        stream_type="sensor_info",
        recordable_type_id="ForwardCamera",
        flavor="RealSense_D435i_Sensor2_Info|id:2004"
    ),
    "/device_0/sensor_0/option": StreamConfig(
        stream_id=2005,
        stream_type="options",
        recordable_type_id="ForwardCamera",
        flavor="RealSense_D435i_Options|id:2005"
    ),
}


def create_rgbd_config(compression: str = "lz4", verbose: bool = False) -> ConverterConfig:
    """Create RGB-D converter configuration (Color + Depth + Transform)"""
    return ConverterConfig(
        topic_mapping=RGBD_STREAMS,
        phase="rgbd",
        compression=compression,
        verbose=verbose
    )


def create_rgbd_imu_config(compression: str = "lz4", verbose: bool = False) -> ConverterConfig:
    """Create RGB-D + IMU + Transform + Device/Sensor Info converter configuration"""
    return ConverterConfig(
        topic_mapping=RGBD_IMU_STREAMS,
        phase="rgbd_imu_info",
        compression=compression,
        verbose=verbose
    )
