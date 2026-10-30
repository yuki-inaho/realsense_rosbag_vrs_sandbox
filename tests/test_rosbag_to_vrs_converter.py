"""Converter regression tests using generated ROS1 bags and real VRS files."""

from pathlib import Path

import pytest

from scripts.rosbag_to_vrs_converter import (
    ConversionResult,
    ConverterConfig,
    RosbagToVRSConverter,
    StreamConfig,
)
from scripts.synthetic_rosbag import SyntheticBagSpec, write_synthetic_rosbag
from scripts.vrs_reader import VRSReader


@pytest.fixture
def rgbd_mapping() -> dict[str, StreamConfig]:
    """Select only image streams so their output counts can be checked exactly."""
    return {
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
    }


@pytest.fixture
def rgbd_config(rgbd_mapping: dict[str, StreamConfig]) -> ConverterConfig:
    """Use the production configuration class, including compression selection."""
    return ConverterConfig(topic_mapping=rgbd_mapping, phase="rgbd", compression="lz4")


@pytest.fixture
def synthetic_rosbag_path(tmp_path: Path) -> Path:
    """Generate a small, valid bag without any local recordings or downloads."""
    spec = SyntheticBagSpec(width=8, height=6, frame_count=2)
    return write_synthetic_rosbag(tmp_path / "synthetic.bag", spec)


def test_converter_initialization(
    synthetic_rosbag_path: Path, rgbd_config: ConverterConfig, tmp_path: Path
) -> None:
    """Construction retains the selected paths and configuration."""
    vrs_path = tmp_path / "output.vrs"
    converter = RosbagToVRSConverter(synthetic_rosbag_path, vrs_path, rgbd_config)

    assert converter.rosbag_path == synthetic_rosbag_path
    assert converter.vrs_path == vrs_path
    assert converter.config == rgbd_config


def test_converter_result_has_statistics(
    synthetic_rosbag_path: Path, rgbd_config: ConverterConfig, tmp_path: Path
) -> None:
    """Statistics describe the actual generated files and written data records."""
    vrs_path = tmp_path / "output.vrs"
    result = RosbagToVRSConverter(synthetic_rosbag_path, vrs_path, rgbd_config).convert()

    assert isinstance(result, ConversionResult)
    assert result.input_bag_size == synthetic_rosbag_path.stat().st_size
    assert result.output_vrs_size == vrs_path.stat().st_size > 0
    assert result.compression_ratio == pytest.approx(result.output_vrs_size / result.input_bag_size)
    # A tiny VRS file may be larger than its input because both formats have headers.
    assert result.compression_ratio > 0
    assert result.total_messages == 4
    assert result.messages_per_stream == {1001: 2, 1002: 2}
    assert result.duration_sec > 0
    assert result.conversion_time_sec > 0


def test_converted_vrs_contains_selected_streams_and_configuration(
    synthetic_rosbag_path: Path, rgbd_config: ConverterConfig, tmp_path: Path
) -> None:
    """The real reader finds only requested streams and their camera settings."""
    vrs_path = tmp_path / "output.vrs"
    RosbagToVRSConverter(synthetic_rosbag_path, vrs_path, rgbd_config).convert()

    with VRSReader(vrs_path) as reader:
        assert reader.get_stream_ids() == [1001, 1002]
        color = reader.read_configuration(1001)
        depth = reader.read_configuration(1002)
        assert (color["width"], color["height"], color["encoding"]) == (8, 6, "rgb8")
        assert (depth["width"], depth["height"], depth["encoding"]) == (8, 6, "16UC1")
        assert len(color["camera_k"]) == len(depth["camera_k"]) == 9
        assert depth["depth_scale"] == pytest.approx(0.002)


def test_converted_vrs_has_data_records(
    synthetic_rosbag_path: Path, rgbd_config: ConverterConfig, tmp_path: Path
) -> None:
    """Iterators return all image payloads, including the last queued record."""
    vrs_path = tmp_path / "output.vrs"
    RosbagToVRSConverter(synthetic_rosbag_path, vrs_path, rgbd_config).convert()

    with VRSReader(vrs_path) as reader:
        color = list(reader.read_data_records(1001))
        depth = list(reader.read_data_records(1002))
        assert len(color) == len(depth) == 2
        assert all(len(record["data"]) == 8 * 6 * 3 for record in color)
        assert all(len(record["data"]) == 8 * 6 * 2 for record in depth)
        assert color[0]["timestamp"] < color[-1]["timestamp"]
        assert depth[0]["timestamp"] < depth[-1]["timestamp"]


def test_converter_error_on_missing_rosbag(rgbd_config: ConverterConfig, tmp_path: Path) -> None:
    """A missing input is reported without creating an output."""
    vrs_path = tmp_path / "output.vrs"
    converter = RosbagToVRSConverter(tmp_path / "nonexistent.bag", vrs_path, rgbd_config)

    with pytest.raises(FileNotFoundError):
        converter.convert()
    assert not vrs_path.exists()


def test_converter_error_on_invalid_output_path(
    synthetic_rosbag_path: Path, rgbd_config: ConverterConfig, tmp_path: Path
) -> None:
    """An existing file cannot be used as the output's parent directory."""
    parent_file = tmp_path / "not-a-directory"
    parent_file.write_text("keep this file", encoding="utf-8")
    invalid_vrs = parent_file / "output.vrs"
    converter = RosbagToVRSConverter(synthetic_rosbag_path, invalid_vrs, rgbd_config)

    with pytest.raises((OSError, RuntimeError)):
        converter.convert()
    assert parent_file.read_text(encoding="utf-8") == "keep this file"


def test_full_bag_duration_and_repeated_conversion_statistics(
    rgbd_config: ConverterConfig, tmp_path: Path
) -> None:
    """Longer intervals must not be truncated at one second or accumulate counts."""
    spec = SyntheticBagSpec(width=8, height=6, frame_count=3, frame_period_ns=1_100_000_000)
    bag_path = write_synthetic_rosbag(tmp_path / "long-interval.bag", spec)
    converter = RosbagToVRSConverter(bag_path, tmp_path / "first.vrs", rgbd_config)
    first = converter.convert()
    # Static metadata are 1 ms before the first frame; final gyro is 2 ms after the last.
    expected_duration = ((spec.frame_count - 1) * spec.frame_period_ns + 3_000_000) / 1e9
    assert first.duration_sec == pytest.approx(expected_duration, rel=0, abs=1e-9)
    converter.vrs_path = tmp_path / "second.vrs"
    second = converter.convert()
    assert second.duration_sec == first.duration_sec
    assert second.total_messages == first.total_messages == 6
    assert second.messages_per_stream == first.messages_per_stream == {1001: 3, 1002: 3}
