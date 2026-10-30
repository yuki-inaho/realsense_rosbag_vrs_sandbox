"""
ROSbag to VRS Converter

Converts RealSense D435i ROSbag files to VRS format.
Color + Depth (必須)
"""

import math
import struct
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from inspect import Parameter, signature
from pathlib import Path
from typing import Any, cast

# ROSbag reader (support both ROS1 and ROS2 via AnyReader)
try:
    from rosbags.highlevel import AnyReader
except ImportError:
    raise ImportError("rosbags library is required. Install with: uv add rosbags")

# VRS writer
from scripts.image_payload import image_description, image_payload
from scripts.rosbag_deserializer import deserialize_reader_message
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


ReaderFactory = Callable[..., Any]
WriterFactory = Callable[[Path], Any]


class RosbagToVRSConverter:
    """
    ROSbag to VRS converter (Color + Depth)

    DRY/KISS/SOLID principles:
    - Single Responsibility: Only handles ROSbag -> VRS conversion
    - Open/Closed: New streams can be added via StreamConfig without modifying core logic
    - Dependency Inversion: Uses abstract VRSWriter interface
    """

    def __init__(
        self,
        rosbag_path: Path,
        vrs_path: Path,
        config: ConverterConfig,
        reader_factory: ReaderFactory | None = None,
        writer_factory: WriterFactory | None = None,
    ) -> None:
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
        self._reader_factory = reader_factory
        self._writer_factory = writer_factory

        self._stats: dict[str, Any] = {}
        self._reset_statistics()

    def _reset_statistics(self) -> None:
        """Keep repeated conversions independent and release previous frame buffers."""
        self._stats = {
            "total_messages": 0,
            "messages_per_stream": {},
            "sample_headers": {},
            "image_configurations": {},
            "camera_info_cache": {},  # Cache CameraInfo messages
            "transform_cache": {},  # Cache Transform messages
            "stream_info_cache": {},  # Cache StreamInfo messages
            "device_info_cache": {},  # Cache Device Info KeyValue pairs
            "sensor_info_cache": {},  # Cache Sensor Info messages
            "options_cache": {},  # Cache Options messages
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

        if self.rosbag_path.resolve() == self.vrs_path.resolve():
            raise ValueError("Input ROSbag and output VRS must be different paths")
        self._reset_statistics()
        start_time = time.perf_counter()

        if self.config.verbose:
            print(f"Converting {self.rosbag_path} -> {self.vrs_path}")
            print(f"Phase: {self.config.phase}, Compression: {self.config.compression}")

        # Get input file size
        input_bag_size = self.rosbag_path.stat().st_size

        # Detect ROSbag format (ROS1 or ROS2)
        reader = self._open_rosbag()

        # Open the bag once. All schema/tag information must be collected before
        # the official writer starts its asynchronous, bounded data writes.
        with reader:
            self._cache_camera_info(reader)
            self._cache_sample_headers(reader)
            self._cache_transforms(reader)
            self._cache_stream_info(reader)
            self._cache_device_info(reader)
            self._cache_sensor_info(reader)
            self._cache_options(reader)
            duration_sec = self._calculate_bag_duration(reader)
            with self._create_writer() as writer:
                self._create_streams(writer)
                self._write_configurations(writer)
                self._process_messages(reader, writer)

        output_vrs_size = self.vrs_path.stat().st_size
        conversion_time = time.perf_counter() - start_time

        result = ConversionResult(
            input_bag_size=input_bag_size,
            output_vrs_size=output_vrs_size,
            compression_ratio=output_vrs_size / input_bag_size if input_bag_size > 0 else 0.0,
            total_messages=self._stats["total_messages"],
            messages_per_stream=self._stats["messages_per_stream"].copy(),
            duration_sec=duration_sec,
            conversion_time_sec=conversion_time,
        )

        if self.config.verbose:
            print(f"Conversion complete in {conversion_time:.2f}s")
            input_mb = input_bag_size / 1024 / 1024
            output_mb = output_vrs_size / 1024 / 1024
            print(f"Input: {input_mb:.2f} MB -> Output: {output_mb:.2f} MB")
            print(f"Compression ratio: {result.compression_ratio:.2%}")
            print(f"Total messages: {result.total_messages}")
            print(f"Messages per stream: {result.messages_per_stream}")

        return result

    def _open_rosbag(self) -> Any:  # Returns AnyReader
        """Open ROSbag with auto-detection of format (ROS1 or ROS2)"""
        # AnyReader automatically detects ROSbag1 or ROSbag2 format
        try:
            if self._reader_factory is None:
                return AnyReader([self.rosbag_path])
            if self._factory_accepts_required_positional_arg(self._reader_factory):
                return self._reader_factory([self.rosbag_path])
            return self._reader_factory()
        except Exception as e:
            raise ValueError(f"Cannot open ROSbag: {e}") from e

    def _create_writer(self) -> Any:
        """Create a VRS writer, allowing tests to inject a recording double."""
        if self._writer_factory is not None:
            return self._writer_factory(self.vrs_path)
        return VRSWriter(str(self.vrs_path), compression=self.config.compression)

    @staticmethod
    def _factory_accepts_required_positional_arg(factory: ReaderFactory) -> bool:
        try:
            sig = signature(factory)
        except (TypeError, ValueError):
            return True

        for parameter in sig.parameters.values():
            if parameter.kind == Parameter.VAR_POSITIONAL:
                return True
            if (
                parameter.kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD)
                and parameter.default is Parameter.empty
            ):
                return True
        return False

    def _create_streams(self, writer: VRSWriter) -> None:
        """Create VRS streams based on topic mapping"""
        for topic, stream_config in self.config.topic_mapping.items():
            # VRSWriter.add_stream() accepts (stream_id, stream_name)
            # stream_name is automatically encoded with |id:stream_id format
            writer.add_stream(stream_config.stream_id, stream_config.flavor)

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
            "/device_0/sensor_0/Depth_0/info/camera_info",
        ]

        connections = [x for x in reader.connections if x.topic in camera_info_topics]

        for connection, timestamp, rawdata in reader.messages(connections=connections):
            # Deserialize message
            msg = deserialize_reader_message(reader, rawdata, connection.msgtype)

            # Cache by topic
            self._stats["camera_info_cache"][connection.topic] = msg

            if self.config.verbose:
                print(f"Cached CameraInfo from {connection.topic}")

            # Stop after getting one message per topic
            if len(self._stats["camera_info_cache"]) >= len(camera_info_topics):
                break

    def _cache_sample_headers(self, reader: Any) -> None:
        """Inspect initial image/IMU messages before freezing VRS configurations."""
        topics = {
            topic
            for topic, stream in self.config.topic_mapping.items()
            if stream.stream_type in {"color", "depth", "imu_accel", "imu_gyro"}
        }
        connections = [
            connection for connection in reader.connections if connection.topic in topics
        ]
        if not connections:
            return
        for connection, _, rawdata in reader.messages(connections=connections):
            if connection.topic not in self._stats["sample_headers"]:
                self._stats["sample_headers"][connection.topic] = deserialize_reader_message(
                    reader, rawdata, connection.msgtype
                )
            if len(self._stats["sample_headers"]) == len(connections):
                break

    def _cache_transforms(self, reader: Any) -> None:
        """
        Cache Transform messages for Configuration records

        Transform topics:
        - /device_0/sensor_0/Depth_0/tf/0 (Depth Extrinsic)
        - /device_0/sensor_1/Color_0/tf/0 (Color Extrinsic)
        """
        transform_topics = ["/device_0/sensor_0/Depth_0/tf/0", "/device_0/sensor_1/Color_0/tf/0"]

        connections = [x for x in reader.connections if x.topic in transform_topics]

        # Transform topics may not exist in all bags (optional)
        if not connections:
            if self.config.verbose:
                print("No Transform topics found in ROSbag (skipping)")
            return

        for connection, timestamp, rawdata in reader.messages(connections=connections):
            # Deserialize message
            msg = deserialize_reader_message(reader, rawdata, connection.msgtype)

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
            "/device_0/sensor_2/Gyro_0/info",
        ]

        connections = [x for x in reader.connections if x.topic in stream_info_topics]

        if not connections:
            if self.config.verbose:
                print("No StreamInfo topics found in ROSbag (skipping)")
            return

        for connection, timestamp, rawdata in reader.messages(connections=connections):
            msg = deserialize_reader_message(reader, rawdata, connection.msgtype)
            self._stats["stream_info_cache"][connection.topic] = msg

            if self.config.verbose:
                stream_info = f"fps={msg.fps}, encoding={msg.encoding}"
                print(f"Cached StreamInfo from {connection.topic}: {stream_info}")

    def _cache_device_info(self, reader: Any) -> None:
        """
        Cache Device Info messages

        Device Info topics:
        - /device_0/info (multiple KeyValue pairs)
        """
        device_info_topic = "/device_0/info"
        device_info_dict = {}

        connections = [x for x in reader.connections if x.topic == device_info_topic]

        if not connections:
            if self.config.verbose:
                print("No Device Info topics found in ROSbag (skipping)")
            return

        for connection, timestamp, rawdata in reader.messages(connections=connections):
            msg = deserialize_reader_message(reader, rawdata, connection.msgtype)
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
            "/device_0/sensor_2/info",
        ]

        connections = [x for x in reader.connections if x.topic in sensor_info_topics]

        if not connections:
            if self.config.verbose:
                print("No Sensor Info topics found in ROSbag (skipping)")
            return

        for connection, timestamp, rawdata in reader.messages(connections=connections):
            msg = deserialize_reader_message(reader, rawdata, connection.msgtype)
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

        # Find all option topics
        option_connections = [c for c in reader.connections if "/option/" in c.topic]

        if not option_connections:
            if self.config.verbose:
                print("No Options topics found in ROSbag (skipping)")
            return

        for connection, timestamp, rawdata in reader.messages(connections=option_connections):
            msg = deserialize_reader_message(reader, rawdata, connection.msgtype)

            # Parse topic: /device_0/sensor_X/option/OPTION_NAME/TYPE
            parts = connection.topic.split("/")
            if len(parts) < 6:
                continue  # Invalid topic format

            sensor_id = parts[2]  # sensor_0, sensor_1, sensor_2
            option_name = parts[4]  # Exposure, Gain, etc.
            option_type = parts[5]  # value or description

            # The same option name can appear on multiple sensors.
            option_key = (sensor_id, option_name)
            if option_key not in options_dict:
                options_dict[option_key] = {
                    "name": option_name,
                    "sensor": sensor_id,
                    "value": None,
                    "description": None,
                }

            # Store value or description
            if option_type == "value":
                options_dict[option_key]["value"] = float(msg.data)
            elif option_type == "description":
                options_dict[option_key]["description"] = str(msg.data)

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

    def _write_color_configuration(
        self, writer: VRSWriter, stream_config: StreamConfig, topic: str
    ) -> None:
        self._write_image_configuration(writer, stream_config, topic)

    def _write_depth_configuration(
        self, writer: VRSWriter, stream_config: StreamConfig, topic: str
    ) -> None:
        self._write_image_configuration(writer, stream_config, topic)

    @staticmethod
    def _camera_array(camera_info: Any, field: str) -> list[float]:
        """Handle ROS1's upper-case and ROS2's lower-case calibration fields."""
        values = getattr(camera_info, field, None)
        if values is None:
            values = getattr(camera_info, field.lower(), ())
        if values is None:
            return []
        return [float(value) for value in values]

    def _write_image_configuration(
        self, writer: VRSWriter, stream_config: StreamConfig, topic: str
    ) -> None:
        base_topic = topic.removesuffix("/image/data")
        camera_info_topic = f"{base_topic}/info/camera_info"
        camera_info = self._stats["camera_info_cache"].get(camera_info_topic)
        if camera_info is None:
            raise ValueError(f"CameraInfo not found for {camera_info_topic}")
        stream_info = self._stats["stream_info_cache"].get(f"{base_topic}/info")
        is_depth = stream_config.stream_type == "depth"
        config_data: dict[str, Any] = {
            "width": int(camera_info.width),
            "height": int(camera_info.height),
            "encoding": "16UC1" if is_depth else "rgb8",
            "camera_k": self._camera_array(camera_info, "K"),
            "camera_d": self._camera_array(camera_info, "D"),
            "camera_r": self._camera_array(camera_info, "R"),
            "camera_p": self._camera_array(camera_info, "P"),
            "distortion_model": str(camera_info.distortion_model),
            "frame_id": str(camera_info.header.frame_id),
        }
        if stream_info is not None:
            config_data.update(
                fps=int(stream_info.fps),
                encoding=str(stream_info.encoding),
                is_recommended=bool(stream_info.is_recommended),
            )
        image = self._stats["sample_headers"].get(topic)
        if image is not None:
            description = image_description(image)
            if (description["width"], description["height"]) != (
                config_data["width"],
                config_data["height"],
            ):
                raise ValueError(f"Image dimensions disagree with CameraInfo for {topic}")
            config_data.update(description)
            config_data["source_encoding"] = str(image.encoding)
        if is_depth:
            scale, source = self._depth_scale(topic)
            config_data["depth_scale"] = scale
            config_data["depth_scale_source"] = source
        self._stats["image_configurations"][stream_config.stream_id] = config_data
        writer.write_configuration(stream_config.stream_id, config_data)
        if self.config.verbose:
            print(
                f"Configured {stream_config.stream_type} stream {stream_config.stream_id}: "
                f"{config_data['width']}x{config_data['height']} {config_data['encoding']}"
            )

    def _depth_scale(self, topic: str) -> tuple[float, str]:
        """Use recorded Depth Units when available, otherwise retain the explicit default."""
        sensor_id = topic.split("/")[2]
        for option in self._stats["options_cache"].values():
            name = option["name"].lower().replace(" ", "").replace("_", "")
            if option["sensor"] == sensor_id and name == "depthunits":
                value = option["value"]
                if value is None:
                    continue
                scale = float(value)
                if not math.isfinite(scale) or scale <= 0:
                    raise ValueError("Recorded Depth Units must be finite and positive")
                return scale, "recorded_depth_units"
        return 0.001, "default_millimeters"

    def _write_imu_accel_configuration(
        self, writer: VRSWriter, stream_config: StreamConfig, topic: str
    ) -> None:
        self._write_imu_configuration(writer, stream_config, topic, "accelerometer", "m/s^2")

    def _write_imu_gyro_configuration(
        self, writer: VRSWriter, stream_config: StreamConfig, topic: str
    ) -> None:
        self._write_imu_configuration(writer, stream_config, topic, "gyroscope", "rad/s")

    def _write_imu_configuration(
        self,
        writer: VRSWriter,
        stream_config: StreamConfig,
        topic: str,
        sensor_type: str,
        unit: str,
    ) -> None:
        """Preserve recorded IMU settings; never invent a rate or noise calibration."""
        message = self._stats["sample_headers"].get(topic)
        header = getattr(message, "header", None)
        stream_info = self._stats["stream_info_cache"].get(
            topic.removesuffix("/imu/data") + "/info"
        )
        config_data: dict[str, Any] = {
            "sensor_type": sensor_type,
            "frame_id": str(getattr(header, "frame_id", "")),
            "unit": unit,
            "sample_rate": float(stream_info.fps) if stream_info is not None else None,
            "axes": ["x", "y", "z"],
            "range": None,
            "noise_variances": None,
            "bias_variances": None,
        }
        if stream_info is not None:
            config_data.update(
                fps=int(stream_info.fps),
                encoding=str(stream_info.encoding),
                is_recommended=bool(stream_info.is_recommended),
            )
        writer.write_configuration(stream_config.stream_id, config_data)
        if self.config.verbose:
            print(f"Configured {sensor_type} stream {stream_config.stream_id}")

    def _write_transform_depth_configuration(
        self, writer: VRSWriter, stream_config: StreamConfig, topic: str
    ) -> None:
        """Write Depth Extrinsic Configuration record"""
        transform_msg = self._stats["transform_cache"].get(topic)

        if transform_msg is None:
            # Default to identity transform if not found
            config_data = {
                "transform_type": "static",
                "sensor_name": "Depth",
                "reference_frame": "device_0",
                "translation": {"x": 0.0, "y": 0.0, "z": 0.0, "unit": "meters"},
                "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0, "format": "quaternion"},
            }
            if self.config.verbose:
                print("Depth Transform not found, using identity transform (default)")
        else:
            config_data = {
                "transform_type": "static",
                "sensor_name": "Depth",
                "reference_frame": "device_0",
                "translation": {
                    "x": float(transform_msg.translation.x),
                    "y": float(transform_msg.translation.y),
                    "z": float(transform_msg.translation.z),
                    "unit": "meters",
                },
                "rotation": {
                    "x": float(transform_msg.rotation.x),
                    "y": float(transform_msg.rotation.y),
                    "z": float(transform_msg.rotation.z),
                    "w": float(transform_msg.rotation.w),
                    "format": "quaternion",
                },
            }

        writer.write_configuration(stream_config.stream_id, config_data)

        if self.config.verbose:
            translation = cast(dict[str, Any], config_data["translation"])
            translation_text = (
                f"({translation['x']:.6f}, {translation['y']:.6f}, {translation['z']:.6f})"
            )
            print(
                f"Wrote Configuration for stream {stream_config.stream_id} (Depth Extrinsic): "
                f"T={translation_text}"
            )

    def _write_transform_color_configuration(
        self, writer: VRSWriter, stream_config: StreamConfig, topic: str
    ) -> None:
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
                "unit": "meters",
            },
            "rotation": {
                "x": float(transform_msg.rotation.x),
                "y": float(transform_msg.rotation.y),
                "z": float(transform_msg.rotation.z),
                "w": float(transform_msg.rotation.w),
                "format": "quaternion",
            },
        }

        writer.write_configuration(stream_config.stream_id, config_data)

        if self.config.verbose:
            translation = cast(dict[str, Any], config_data["translation"])
            translation_text = (
                f"({translation['x']:.6f}, {translation['y']:.6f}, {translation['z']:.6f})"
            )
            print(
                f"Wrote Configuration for stream {stream_config.stream_id} (Color Extrinsic): "
                f"T={translation_text}"
            )

    def _write_device_info_configuration(
        self, writer: VRSWriter, stream_config: StreamConfig, topic: str
    ) -> None:
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
            "recommended_firmware_version": device_info_dict.get(
                "Recommended Firmware Version", ""
            ),
            "physical_port": device_info_dict.get("Physical Port", ""),
            "debug_op_code": device_info_dict.get("Debug Op Code", ""),
            "advanced_mode": device_info_dict.get("Advanced Mode", ""),
            "product_id": device_info_dict.get("Product Id", ""),
            "usb_type_descriptor": device_info_dict.get("Usb Type Descriptor", ""),
        }

        writer.write_configuration(stream_config.stream_id, config_data)

        if self.config.verbose:
            device_name = config_data["device_name"]
            serial_number = config_data["serial_number"]
            print(
                f"Wrote Configuration for stream {stream_config.stream_id} "
                f"(Device Info): {device_name} (SN: {serial_number})"
            )

    def _write_sensor_info_configuration(
        self, writer: VRSWriter, stream_config: StreamConfig, topic: str
    ) -> None:
        """Write Sensor Info Configuration record"""
        sensor_info_msg = self._stats["sensor_info_cache"].get(topic)

        if sensor_info_msg is None:
            if self.config.verbose:
                print(
                    f"Sensor Info not found for {topic}, skipping stream {stream_config.stream_id}"
                )
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
            "associated_streams": associated_streams,
        }

        writer.write_configuration(stream_config.stream_id, config_data)

        if self.config.verbose:
            sensor_name = config_data["sensor_name"]
            print(
                f"Wrote Configuration for stream {stream_config.stream_id} "
                f"(Sensor Info): {sensor_name} ({sensor_id})"
            )

    def _write_options_configuration(
        self, writer: VRSWriter, stream_config: StreamConfig, topic: str
    ) -> None:
        """Write Options Configuration record"""
        options_dict = self._stats.get("options_cache", {})

        if not options_dict:
            if self.config.verbose:
                print(f"No Options found in ROSbag, skipping stream {stream_config.stream_id}")
            return

        # Build options array
        options_array = []
        for _, data in sorted(options_dict.items()):
            options_array.append(
                {
                    "name": data["name"],
                    "sensor": data["sensor"],
                    "value": data["value"],
                    "description": data["description"],
                }
            )

        config_data = {
            "info_type": "options",
            "total_options": len(options_array),
            "options": options_array,
        }

        writer.write_configuration(stream_config.stream_id, config_data)

        if self.config.verbose:
            option_count = len(options_array)
            print(
                f"Wrote Configuration for stream {stream_config.stream_id} "
                f"(Options): {option_count} options"
            )

    def _process_messages(self, reader: Any, writer: VRSWriter) -> None:
        """Process all messages in temporal order"""
        target_topics = list(self.config.topic_mapping.keys())

        connections = [x for x in reader.connections if x.topic in target_topics]

        if not connections:
            raise ValueError(f"No messages found for topics: {target_topics}")

        for connection, timestamp, rawdata in reader.messages(connections=connections):
            # Get stream config
            stream_config = self.config.topic_mapping.get(connection.topic)
            if stream_config is None:
                continue  # Skip topics not in mapping

            # Deserialize message
            msg = deserialize_reader_message(reader, rawdata, connection.msgtype)

            # Convert and write based on stream type
            if stream_config.stream_type == "color":
                self._process_color_message(writer, stream_config, msg, timestamp)
            elif stream_config.stream_type == "depth":
                self._process_depth_message(writer, stream_config, msg, timestamp)
            elif stream_config.stream_type == "imu_accel":
                self._process_imu_accel_message(writer, stream_config, msg, timestamp)
            elif stream_config.stream_type == "imu_gyro":
                self._process_imu_gyro_message(writer, stream_config, msg, timestamp)
            else:
                continue

            # Count emitted Data records, not configuration-only source messages.
            self._stats["total_messages"] += 1
            self._stats["messages_per_stream"][stream_config.stream_id] += 1

    def _process_color_message(
        self, writer: VRSWriter, stream_config: StreamConfig, msg: Any, timestamp: int
    ) -> None:
        self._process_image_message(writer, stream_config, msg, timestamp)

    def _process_depth_message(
        self, writer: VRSWriter, stream_config: StreamConfig, msg: Any, timestamp: int
    ) -> None:
        self._process_image_message(writer, stream_config, msg, timestamp)

    def _process_image_message(
        self, writer: VRSWriter, stream_config: StreamConfig, msg: Any, timestamp: int
    ) -> None:
        """Preserve image values while removing ROS row padding and big-endian storage."""
        configuration = self._stats["image_configurations"][stream_config.stream_id]
        payload = image_payload(msg, configuration)
        writer.write_data(stream_config.stream_id, timestamp / 1e9, payload)

    def _process_imu_accel_message(
        self, writer: VRSWriter, stream_config: StreamConfig, msg: Any, timestamp: int
    ) -> None:
        """Process IMU Accelerometer message"""
        # Convert timestamp (nanoseconds -> seconds)
        timestamp_sec = timestamp / 1e9

        # Extract linear acceleration (x, y, z) from sensor_msgs/Imu
        # Pack as 3 doubles (24 bytes)
        imu_data = struct.pack(
            "<ddd", msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z
        )

        # Write Data record (timestamp + 24 bytes)
        writer.write_data(stream_config.stream_id, timestamp_sec, imu_data)

    def _process_imu_gyro_message(
        self, writer: VRSWriter, stream_config: StreamConfig, msg: Any, timestamp: int
    ) -> None:
        """Process IMU Gyroscope message"""
        # Convert timestamp (nanoseconds -> seconds)
        timestamp_sec = timestamp / 1e9

        # Extract angular velocity (x, y, z) from sensor_msgs/Imu
        # Pack as 3 doubles (24 bytes)
        imu_data = struct.pack(
            "<ddd", msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z
        )

        # Write Data record (timestamp + 24 bytes)
        writer.write_data(stream_config.stream_id, timestamp_sec, imu_data)

    def _calculate_bag_duration(self, reader: Any) -> float:
        """Return exact first-to-last message duration, not an early sample."""
        start = getattr(reader, "start_time", None)
        end = getattr(reader, "end_time", None)
        if isinstance(start, int) and isinstance(end, int):
            # rosbags uses an exclusive end timestamp (last message + 1 ns).
            return max(0.0, (end - start - 1) / 1e9)
        timestamps = (timestamp for _, timestamp, _ in reader.messages())
        first = next(timestamps, None)
        if first is None:
            return 0.0
        last = first
        for last in timestamps:
            pass
        return float(max(0.0, (last - first) / 1e9))


# RGB-D stream mapping (Color + Depth + Transform)
RGBD_STREAMS = {
    "/device_0/sensor_1/Color_0/image/data": StreamConfig(
        stream_id=1001,
        stream_type="color",
        recordable_type_id="ForwardCamera",
        flavor="RealSense_D435i_Color|id:1001",
    ),
    "/device_0/sensor_0/Depth_0/image/data": StreamConfig(
        stream_id=1002,
        stream_type="depth",
        recordable_type_id="ForwardCamera",
        flavor="RealSense_D435i_Depth|id:1002",
    ),
    "/device_0/sensor_0/Depth_0/tf/0": StreamConfig(
        stream_id=1005,
        stream_type="transform_depth",
        recordable_type_id="ForwardCamera",
        flavor="RealSense_D435i_Depth_Extrinsic|id:1005",
    ),
    "/device_0/sensor_1/Color_0/tf/0": StreamConfig(
        stream_id=1006,
        stream_type="transform_color",
        recordable_type_id="ForwardCamera",
        flavor="RealSense_D435i_Color_Extrinsic|id:1006",
    ),
}


# RGB-D + IMU stream mapping (Transform included via RGBD_STREAMS)
RGBD_IMU_STREAMS = {
    **RGBD_STREAMS,
    "/device_0/sensor_2/Accel_0/imu/data": StreamConfig(
        stream_id=1003,
        stream_type="imu_accel",
        recordable_type_id="MotionSensor",
        flavor="RealSense_D435i_Accel|id:1003",
    ),
    "/device_0/sensor_2/Gyro_0/imu/data": StreamConfig(
        stream_id=1004,
        stream_type="imu_gyro",
        recordable_type_id="MotionSensor",
        flavor="RealSense_D435i_Gyro|id:1004",
    ),
    "/device_0/info": StreamConfig(
        stream_id=2001,
        stream_type="device_info",
        recordable_type_id="ForwardCamera",
        flavor="RealSense_D435i_Device_Info|id:2001",
    ),
    "/device_0/sensor_0/info": StreamConfig(
        stream_id=2002,
        stream_type="sensor_info",
        recordable_type_id="ForwardCamera",
        flavor="RealSense_D435i_Sensor0_Info|id:2002",
    ),
    "/device_0/sensor_1/info": StreamConfig(
        stream_id=2003,
        stream_type="sensor_info",
        recordable_type_id="ForwardCamera",
        flavor="RealSense_D435i_Sensor1_Info|id:2003",
    ),
    "/device_0/sensor_2/info": StreamConfig(
        stream_id=2004,
        stream_type="sensor_info",
        recordable_type_id="ForwardCamera",
        flavor="RealSense_D435i_Sensor2_Info|id:2004",
    ),
    "/device_0/sensor_0/option": StreamConfig(
        stream_id=2005,
        stream_type="options",
        recordable_type_id="ForwardCamera",
        flavor="RealSense_D435i_Options|id:2005",
    ),
}


def create_rgbd_config(compression: str = "lz4", verbose: bool = False) -> ConverterConfig:
    """Create RGB-D converter configuration (Color + Depth + Transform)"""
    return ConverterConfig(
        topic_mapping=RGBD_STREAMS, phase="rgbd", compression=compression, verbose=verbose
    )


def create_rgbd_imu_config(compression: str = "lz4", verbose: bool = False) -> ConverterConfig:
    """Create RGB-D + IMU + Transform + Device/Sensor Info converter configuration"""
    return ConverterConfig(
        topic_mapping=RGBD_IMU_STREAMS,
        phase="rgbd_imu_info",
        compression=compression,
        verbose=verbose,
    )
