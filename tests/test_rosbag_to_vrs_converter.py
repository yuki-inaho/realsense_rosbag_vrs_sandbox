"""
Test cases for ROSbag to VRS Converter (Phase 4A: Color + Depth)

TDD RED Phase: Test cases created before implementation.
"""
import pytest
from pathlib import Path
from dataclasses import dataclass
from typing import Dict


# Data classes (must be imported from actual implementation later)
@dataclass
class StreamConfig:
    """Stream configuration"""
    stream_id: int
    stream_type: str  # "color", "depth", "imu_accel", "imu_gyro"
    recordable_type_id: str  # "ForwardCamera", "MotionSensor"
    flavor: str


@dataclass
class ConverterConfig:
    """Converter configuration"""
    topic_mapping: Dict[str, StreamConfig]
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
    messages_per_stream: Dict[int, int]  # stream_id -> count
    duration_sec: float
    conversion_time_sec: float


# Fixtures
@pytest.fixture
def phase_4a_mapping() -> Dict[str, StreamConfig]:
    """Phase 4A topic mapping (Color + Depth only)"""
    return {
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


@pytest.fixture
def phase_4a_config(phase_4a_mapping) -> ConverterConfig:
    """Phase 4A converter configuration"""
    return ConverterConfig(
        topic_mapping=phase_4a_mapping,
        phase="4A",
        compression="lz4",
        verbose=False
    )


@pytest.fixture
def sample_rosbag_path() -> Path:
    """Path to sample ROSbag file (may not exist yet)"""
    return Path("/home/user/realsense_rosbag_vrs_sandbox/data/rosbag/d435i_sample_data.bag")


# Test cases
def test_converter_config_creation(phase_4a_config):
    """ConverterConfig can be created with Phase 4A settings"""
    assert phase_4a_config.phase == "4A"
    assert len(phase_4a_config.topic_mapping) == 2
    assert phase_4a_config.compression == "lz4"
    assert phase_4a_config.verbose is False


def test_stream_config_color(phase_4a_mapping):
    """Color stream config is correctly defined"""
    color_config = phase_4a_mapping["/device_0/sensor_1/Color_0/image/data"]
    assert color_config.stream_id == 1001
    assert color_config.stream_type == "color"
    assert color_config.recordable_type_id == "ForwardCamera"
    assert "Color" in color_config.flavor
    assert "id:1001" in color_config.flavor


def test_stream_config_depth(phase_4a_mapping):
    """Depth stream config is correctly defined"""
    depth_config = phase_4a_mapping["/device_0/sensor_0/Depth_0/image/data"]
    assert depth_config.stream_id == 1002
    assert depth_config.stream_type == "depth"
    assert depth_config.recordable_type_id == "ForwardCamera"
    assert "Depth" in depth_config.flavor
    assert "id:1002" in depth_config.flavor


def test_converter_initialization(sample_rosbag_path, phase_4a_config, tmp_path):
    """Converter can be initialized with paths and config"""
    from scripts.rosbag_to_vrs_converter import RosbagToVRSConverter

    vrs_path = tmp_path / "output.vrs"
    converter = RosbagToVRSConverter(sample_rosbag_path, vrs_path, phase_4a_config)

    assert converter is not None
    assert converter.rosbag_path == sample_rosbag_path
    assert converter.vrs_path == vrs_path
    assert converter.config == phase_4a_config


def test_converter_convert_creates_vrs_file(sample_rosbag_path, phase_4a_config, tmp_path):
    """Converter.convert() creates a VRS file"""
    pytest.skip("Requires actual ROSbag file")

    from scripts.rosbag_to_vrs_converter import RosbagToVRSConverter

    vrs_path = tmp_path / "output.vrs"
    converter = RosbagToVRSConverter(sample_rosbag_path, vrs_path, phase_4a_config)
    result = converter.convert()

    assert vrs_path.exists()
    assert vrs_path.stat().st_size > 0
    assert isinstance(result, ConversionResult)


def test_converter_result_has_statistics(sample_rosbag_path, phase_4a_config, tmp_path):
    """ConversionResult contains expected statistics"""
    pytest.skip("Requires actual ROSbag file")

    from scripts.rosbag_to_vrs_converter import RosbagToVRSConverter

    vrs_path = tmp_path / "output.vrs"
    converter = RosbagToVRSConverter(sample_rosbag_path, vrs_path, phase_4a_config)
    result = converter.convert()

    assert result.input_bag_size > 0
    assert result.output_vrs_size > 0
    assert 0 < result.compression_ratio <= 1.0
    assert result.total_messages > 0
    assert result.duration_sec > 0
    assert result.conversion_time_sec > 0


def test_converted_vrs_has_correct_streams(sample_rosbag_path, phase_4a_config, tmp_path):
    """Converted VRS file has correct stream IDs (1001, 1002)"""
    pytest.skip("Requires actual ROSbag file")

    from scripts.rosbag_to_vrs_converter import RosbagToVRSConverter
    from scripts.vrs_reader import VRSReader

    vrs_path = tmp_path / "output.vrs"
    converter = RosbagToVRSConverter(sample_rosbag_path, vrs_path, phase_4a_config)
    converter.convert()

    with VRSReader(vrs_path) as reader:
        stream_ids = reader.get_stream_ids()
        assert 1001 in stream_ids  # Color
        assert 1002 in stream_ids  # Depth
        assert len(stream_ids) == 2  # Phase 4A only


def test_converted_vrs_has_configuration_records(sample_rosbag_path, phase_4a_config, tmp_path):
    """Converted VRS file has Configuration records for each stream"""
    pytest.skip("Requires actual ROSbag file")

    from scripts.rosbag_to_vrs_converter import RosbagToVRSConverter
    from scripts.vrs_reader import VRSReader

    vrs_path = tmp_path / "output.vrs"
    converter = RosbagToVRSConverter(sample_rosbag_path, vrs_path, phase_4a_config)
    converter.convert()

    with VRSReader(vrs_path) as reader:
        # Color stream configuration
        color_config = reader.read_configuration(1001)
        assert color_config is not None
        assert "width" in color_config
        assert "height" in color_config
        assert "encoding" in color_config

        # Depth stream configuration
        depth_config = reader.read_configuration(1002)
        assert depth_config is not None
        assert "width" in depth_config
        assert "height" in depth_config
        assert "depth_scale" in depth_config


def test_converted_vrs_has_data_records(sample_rosbag_path, phase_4a_config, tmp_path):
    """Converted VRS file has Data records"""
    pytest.skip("Requires actual ROSbag file")

    from scripts.rosbag_to_vrs_converter import RosbagToVRSConverter
    from scripts.vrs_reader import VRSReader

    vrs_path = tmp_path / "output.vrs"
    converter = RosbagToVRSConverter(sample_rosbag_path, vrs_path, phase_4a_config)
    converter.convert()

    with VRSReader(vrs_path) as reader:
        # Color stream data
        color_records = reader.read_data_records(1001)
        assert len(color_records) > 0

        # Depth stream data
        depth_records = reader.read_data_records(1002)
        assert len(depth_records) > 0


def test_converter_error_on_missing_rosbag(phase_4a_config, tmp_path):
    """Converter raises error when ROSbag file is missing"""
    from scripts.rosbag_to_vrs_converter import RosbagToVRSConverter

    missing_bag = tmp_path / "nonexistent.bag"
    vrs_path = tmp_path / "output.vrs"

    converter = RosbagToVRSConverter(missing_bag, vrs_path, phase_4a_config)

    with pytest.raises(FileNotFoundError):
        converter.convert()


def test_converter_error_on_invalid_output_path(sample_rosbag_path, phase_4a_config):
    """Converter raises error when output path is invalid"""
    pytest.skip("Requires actual ROSbag file")

    from scripts.rosbag_to_vrs_converter import RosbagToVRSConverter

    invalid_vrs = Path("/invalid/directory/output.vrs")

    converter = RosbagToVRSConverter(sample_rosbag_path, invalid_vrs, phase_4a_config)

    with pytest.raises((OSError, PermissionError)):
        converter.convert()
