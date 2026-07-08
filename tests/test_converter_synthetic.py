"""Synthetic converter regression tests that do not require a real ROSbag."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from scripts.rosbag_to_vrs_converter import (
    RosbagToVRSConverter,
    create_rgbd_config,
    create_rgbd_imu_config,
)


class RecordingWriter:
    """Minimal writer test double used by the future converter injection point."""

    def __init__(self, filepath: Path | str) -> None:
        self.filepath = Path(filepath)
        self.streams: dict[int, str] = {}
        self.configurations: dict[int, dict[str, Any]] = {}
        self.data_records: dict[int, list[tuple[float, bytes]]] = {}

    def __enter__(self) -> RecordingWriter:
        return self

    def __exit__(self, *args: object) -> None:
        self.filepath.write_bytes(b"synthetic-vrs")

    def add_stream(self, stream_id: int, stream_name: str) -> None:
        self.streams[stream_id] = stream_name
        self.data_records.setdefault(stream_id, [])

    def write_configuration(self, stream_id: int, config_data: dict[str, Any]) -> None:
        self.configurations[stream_id] = config_data

    def write_data(self, stream_id: int, timestamp: float, data: bytes) -> None:
        self.data_records.setdefault(stream_id, []).append((timestamp, data))


class SyntheticReader:
    """Small reader test double matching the rosbags methods used by converter."""

    def __init__(self) -> None:
        self.connections = [
            SimpleNamespace(
                topic="/device_0/sensor_1/Color_0/image/data",
                msgtype="sensor_msgs/msg/Image",
            ),
            SimpleNamespace(
                topic="/device_0/sensor_0/Depth_0/image/data",
                msgtype="sensor_msgs/msg/Image",
            ),
            SimpleNamespace(
                topic="/device_0/sensor_2/Accel_0/imu/data",
                msgtype="sensor_msgs/msg/Imu",
            ),
            SimpleNamespace(
                topic="/device_0/sensor_2/Gyro_0/imu/data",
                msgtype="sensor_msgs/msg/Imu",
            ),
            SimpleNamespace(
                topic="/device_0/sensor_1/Color_0/info/camera_info",
                msgtype="sensor_msgs/msg/CameraInfo",
            ),
            SimpleNamespace(
                topic="/device_0/sensor_0/Depth_0/info/camera_info",
                msgtype="sensor_msgs/msg/CameraInfo",
            ),
            SimpleNamespace(
                topic="/device_0/sensor_0/Depth_0/tf/0",
                msgtype="geometry_msgs/msg/Transform",
            ),
            SimpleNamespace(
                topic="/device_0/sensor_1/Color_0/tf/0",
                msgtype="geometry_msgs/msg/Transform",
            ),
            SimpleNamespace(
                topic="/device_0/sensor_0/Depth_0/info",
                msgtype="realsense2_camera_msgs/msg/StreamInfo",
            ),
            SimpleNamespace(
                topic="/device_0/sensor_1/Color_0/info",
                msgtype="realsense2_camera_msgs/msg/StreamInfo",
            ),
            SimpleNamespace(
                topic="/device_0/sensor_2/Accel_0/info",
                msgtype="realsense2_camera_msgs/msg/StreamInfo",
            ),
            SimpleNamespace(
                topic="/device_0/sensor_2/Gyro_0/info",
                msgtype="realsense2_camera_msgs/msg/StreamInfo",
            ),
            SimpleNamespace(topic="/device_0/info", msgtype="diagnostic_msgs/msg/KeyValue"),
            SimpleNamespace(
                topic="/device_0/sensor_0/info",
                msgtype="std_msgs/msg/String",
            ),
            SimpleNamespace(
                topic="/device_0/sensor_1/info",
                msgtype="std_msgs/msg/String",
            ),
            SimpleNamespace(
                topic="/device_0/sensor_2/info",
                msgtype="std_msgs/msg/String",
            ),
            SimpleNamespace(
                topic="/device_0/sensor_0/option/Exposure/value",
                msgtype="std_msgs/msg/Float64",
            ),
            SimpleNamespace(
                topic="/device_0/sensor_0/option/Exposure/description",
                msgtype="std_msgs/msg/String",
            ),
        ]

    def __enter__(self) -> SyntheticReader:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def messages(self, connections: list[Any] | None = None) -> list[tuple[Any, int, bytes]]:
        selected = connections or self.connections
        return [(connection, 1_000_000_000, connection.topic.encode()) for connection in selected]

    def deserialize(self, rawdata: bytes, msgtype: str) -> Any:
        if msgtype.endswith("Image"):
            return SimpleNamespace(data=rawdata)
        if msgtype.endswith("CameraInfo"):
            return SimpleNamespace(
                width=2,
                height=2,
                K=[1.0, 0.0, 1.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0],
                D=[0.0, 0.0, 0.0, 0.0, 0.0],
                distortion_model="plumb_bob",
                header=SimpleNamespace(frame_id="synthetic_frame"),
            )
        if msgtype.endswith("Transform"):
            vector = SimpleNamespace(x=0.0, y=0.0, z=0.0)
            rotation = SimpleNamespace(x=0.0, y=0.0, z=0.0, w=1.0)
            return SimpleNamespace(translation=vector, rotation=rotation)
        if msgtype.endswith("StreamInfo"):
            encoding = "rgb8" if b"Color" in rawdata else "16UC1"
            return SimpleNamespace(fps=30, encoding=encoding, is_recommended=True)
        if msgtype.endswith("KeyValue"):
            return SimpleNamespace(key="Name", value="Synthetic RealSense")
        if msgtype.endswith("Float64"):
            return SimpleNamespace(data=156.0)
        if msgtype.endswith("String"):
            return SimpleNamespace(data="synthetic", value="Synthetic Sensor")
        vector = SimpleNamespace(x=1.0, y=2.0, z=3.0)
        return SimpleNamespace(linear_acceleration=vector, angular_velocity=vector)


def test_convert_synthetic_rgbd_to_vrs(tmp_path: Path) -> None:
    """RGB-D conversion should run through injected synthetic reader/writer."""
    input_bag = tmp_path / "synthetic.bag"
    input_bag.write_bytes(b"not-a-real-bag")
    output_vrs = tmp_path / "rgbd.vrs"

    converter = RosbagToVRSConverter(
        input_bag,
        output_vrs,
        create_rgbd_config(),
        reader_factory=SyntheticReader,
        writer_factory=RecordingWriter,
    )

    result = converter.convert()

    assert result.messages_per_stream[1001] == 1
    assert result.messages_per_stream[1002] == 1


def test_convert_synthetic_rgbd_imu_to_vrs(tmp_path: Path) -> None:
    """RGB-D+IMU conversion should produce stream counts for 1001-1004."""
    input_bag = tmp_path / "synthetic.bag"
    input_bag.write_bytes(b"not-a-real-bag")
    output_vrs = tmp_path / "rgbd_imu.vrs"

    converter = RosbagToVRSConverter(
        input_bag,
        output_vrs,
        create_rgbd_imu_config(),
        reader_factory=SyntheticReader,
        writer_factory=RecordingWriter,
    )

    result = converter.convert()

    assert result.messages_per_stream[1001] == 1
    assert result.messages_per_stream[1002] == 1
    assert result.messages_per_stream[1003] == 1
    assert result.messages_per_stream[1004] == 1


def test_converter_writes_config_only_streams_without_data_records(tmp_path: Path) -> None:
    """Metadata streams should write configurations without requiring data records."""
    input_bag = tmp_path / "synthetic.bag"
    input_bag.write_bytes(b"not-a-real-bag")
    output_vrs = tmp_path / "config_only.vrs"
    writer = RecordingWriter(output_vrs)

    converter = RosbagToVRSConverter(
        input_bag,
        output_vrs,
        create_rgbd_imu_config(),
        reader_factory=SyntheticReader,
        writer_factory=lambda _: writer,
    )

    converter.convert()

    config_only_streams = {1005, 1006, 2001, 2002, 2003, 2004, 2005}
    assert config_only_streams.issubset(writer.configurations)
    assert all(writer.data_records.get(stream_id, []) == [] for stream_id in config_only_streams)
