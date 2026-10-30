"""Real ROS1 bag -> converter CLI -> official PyVRS reader regression tests.

No reader/writer doubles or private recordings are used.  Expected values
are deserialized from the input bag independently of the converter and are
checked through the official reader, without the repository's VRS reader.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import pyvrs
from rosbags.highlevel import AnyReader

from scripts.synthetic_rosbag import SyntheticBagSpec, write_synthetic_rosbag

pytestmark = pytest.mark.e2e

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_DATA_TOPICS = {
    1001: "/device_0/sensor_1/Color_0/image/data",
    1002: "/device_0/sensor_0/Depth_0/image/data",
    1003: "/device_0/sensor_2/Accel_0/imu/data",
    1004: "/device_0/sensor_2/Gyro_0/imu/data",
}
_CONFIG_ONLY_STREAMS = {1005, 1006, 2001, 2002, 2003, 2004, 2005}


def _run_python(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the user-facing commands in a fresh interpreter."""
    result = subprocess.run(
        [sys.executable, *args],
        cwd=_REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    return result


def _read_input_bag(bag_path: Path) -> dict[str, list[tuple[int, Any]]]:
    messages: dict[str, list[tuple[int, Any]]] = defaultdict(list)
    with AnyReader([bag_path]) as reader:
        for connection, timestamp, rawdata in reader.messages():
            messages[connection.topic].append(
                (timestamp, reader.deserialize(rawdata, connection.msgtype))
            )
    return messages


def _image_from_ros_message(message: Any) -> np.ndarray[Any, Any]:
    """Decode the ROS image contract independently of production helpers."""
    row_bytes = message.width * (3 if message.encoding == "rgb8" else 2)
    packed = np.asarray(message.data, dtype=np.uint8).reshape(message.height, message.step)
    packed = packed[:, :row_bytes].copy()
    if message.encoding == "rgb8":
        return packed.reshape(message.height, message.width, 3)
    endian_dtype = np.dtype(">u2" if message.is_bigendian else "<u2")
    return (
        np.frombuffer(packed.tobytes(), dtype=endian_dtype)
        .reshape(message.height, message.width)
        .astype(np.uint16)
    )


def _check_vrs_against_bag(bag_path: Path, vrs_path: Path, spec: SyntheticBagSpec) -> None:
    """Compare every produced sample and calibration field to the real bag."""
    expected = _read_input_bag(bag_path)
    reader = pyvrs.SyncVRSReader(str(vrs_path))
    # PyVRS otherwise normalizes certain depth formats for display.
    reader.set_image_conversion(pyvrs.ImageConversion.OFF)
    try:
        id_map = {
            stream_id: int(tags["user_stream_id"]) for stream_id, tags in reader.stream_tags.items()
        }
        assert set(id_map.values()) == set(_DATA_TOPICS) | _CONFIG_ONLY_STREAMS
        configurations = {
            id_map[stream_id]: json.loads(tags["config_json"])
            for stream_id, tags in reader.stream_tags.items()
        }
        for stream_id, tags in reader.stream_tags.items():
            assert tags["vrs_sandbox_schema_version"] == "2"
            if id_map[stream_id] in (1001, 1002):
                assert tags["payload_encoding"] == "native_image"
            elif id_map[stream_id] in (1003, 1004):
                assert tags["payload_encoding"] == "imu_xyz_f64le"
        counts: dict[int, int] = defaultdict(int)
        config_counts: dict[int, int] = defaultdict(int)
        all_timestamps: list[float] = []
        for record in reader:
            stream_id = id_map[record.stream_id]
            all_timestamps.append(record.timestamp)
            if record.record_type == "configuration":
                config_counts[stream_id] += 1
                if stream_id in (1001, 1002):
                    metadata = record.metadata_blocks[0]
                    assert metadata["image_width"] == spec.width
                    assert metadata["image_height"] == spec.height
                    pixel_format = (
                        pyvrs.PixelFormat.RGB8 if stream_id == 1001 else pyvrs.PixelFormat.GREY16
                    )
                    assert metadata["image_pixel_format"] == pixel_format.value
                continue
            if record.record_type != "data":
                continue
            assert stream_id in _DATA_TOPICS, "Configuration-only streams must have no Data records"
            index = counts[stream_id]
            timestamp, message = expected[_DATA_TOPICS[stream_id]][index]
            assert record.timestamp == pytest.approx(timestamp / 1e9, rel=0, abs=1e-9)
            if stream_id in (1001, 1002):
                assert record.n_image_blocks == 1
                image = record.image_blocks[0]
                original = _image_from_ros_message(message)
                assert image.shape == original.shape
                assert image.dtype == original.dtype
                np.testing.assert_array_equal(image, original)
            else:
                assert record.n_image_blocks == 0
                vector = (
                    message.linear_acceleration if stream_id == 1003 else message.angular_velocity
                )
                np.testing.assert_array_equal(
                    record.metadata_blocks[0]["doubles"], [vector.x, vector.y, vector.z]
                )
            counts[stream_id] += 1
        assert all_timestamps == sorted(all_timestamps)
        assert dict(counts) == dict.fromkeys(_DATA_TOPICS, spec.frame_count)
        assert dict(config_counts) == dict.fromkeys(set(_DATA_TOPICS) | _CONFIG_ONLY_STREAMS, 1)

        for stream_id, sensor, name, encoding in (
            (1001, 1, "Color", "rgb8"),
            (1002, 0, "Depth", "16UC1"),
        ):
            config = configurations[stream_id]
            camera = expected[f"/device_0/sensor_{sensor}/{name}_0/info/camera_info"][0][1]
            assert config["width"] == camera.width
            assert config["height"] == camera.height
            assert config["encoding"] == encoding
            assert config["frame_id"] == camera.header.frame_id
            assert config["distortion_model"] == camera.distortion_model
            np.testing.assert_array_equal(config["camera_k"], camera.K)
            np.testing.assert_array_equal(config["camera_d"], camera.D)
            np.testing.assert_array_equal(config["camera_r"], camera.R)
            np.testing.assert_array_equal(config["camera_p"], camera.P)
            stream_info = expected[f"/device_0/sensor_{sensor}/{name}_0/info"][0][1]
            assert config["fps"] == stream_info.fps
        assert configurations[1002]["depth_scale"] == spec.depth_scale
        for stream_id, kind, unit in (
            (1003, "accelerometer", "m/s^2"),
            (1004, "gyroscope", "rad/s"),
        ):
            assert configurations[stream_id]["sensor_type"] == kind
            assert configurations[stream_id]["unit"] == unit
            sample = expected[_DATA_TOPICS[stream_id]][0][1]
            info_topic = _DATA_TOPICS[stream_id].removesuffix("/imu/data") + "/info"
            info = expected[info_topic][0][1]
            assert configurations[stream_id]["frame_id"] == sample.header.frame_id
            assert configurations[stream_id]["sample_rate"] == info.fps
            assert configurations[stream_id]["fps"] == info.fps
        for stream_id, sensor, name in ((1005, 0, "Depth"), (1006, 1, "Color")):
            config = configurations[stream_id]
            transform = expected[f"/device_0/sensor_{sensor}/{name}_0/tf/0"][0][1]
            for field, axes in (
                ("translation", ("x", "y", "z")),
                ("rotation", ("x", "y", "z", "w")),
            ):
                for axis in axes:
                    assert config[field][axis] == getattr(getattr(transform, field), axis)

        assert configurations[2001]["device_name"] == "Synthetic RealSense D435i"
        assert configurations[2001]["serial_number"] == "SYNTHETIC-0001"
        assert configurations[2001]["firmware_version"] == "0.0.synthetic"
        for stream_id, name in (
            (2002, "Stereo Module"),
            (2003, "RGB Camera"),
            (2004, "Motion Module"),
        ):
            assert configurations[stream_id]["sensor_name"] == name
        options = {item["name"]: item for item in configurations[2005]["options"]}
        assert configurations[2005]["total_options"] == 2
        assert options["Depth Units"]["value"] == spec.depth_scale
        assert options["Exposure"]["value"] == 156.0
    finally:
        reader.close()


@pytest.mark.parametrize("compression", ["none", "lz4", "zstd"])
def test_synthetic_rgbd_imu_cli_to_official_reader(tmp_path: Path, compression: str) -> None:
    """Real 640x480 bag and VRS files must preserve every pixel/sample."""
    # 12 RGB-D frames exceed the writer's default 16 MiB flush threshold.
    # Checking every later sample catches lost records or timestamp cutoffs.
    spec = SyntheticBagSpec(frame_count=12)
    bag_path = write_synthetic_rosbag(tmp_path / "rgbd_imu.bag", spec)
    vrs_path = tmp_path / "rgbd_imu.vrs"
    with bag_path.open("rb") as bag_file:
        assert bag_file.read(13) == b"#ROSBAG V2.0\n"
    _run_python(
        "convert_to_vrs.py", str(bag_path), str(vrs_path), "--imu", "--compression", compression
    )
    _check_vrs_against_bag(bag_path, vrs_path, spec)


def test_generator_cli_and_padded_big_endian_depth(tmp_path: Path) -> None:
    """Synthetic source CLI also covers padded RGB rows and big-endian depth."""
    spec = SyntheticBagSpec(
        width=8, height=6, frame_count=3, row_padding_bytes=4, depth_bigendian=True
    )
    bag_path, vrs_path = tmp_path / "padded.bag", tmp_path / "padded.vrs"
    _run_python(
        "-m",
        "scripts.synthetic_rosbag",
        str(bag_path),
        "--width",
        str(spec.width),
        "--height",
        str(spec.height),
        "--frames",
        str(spec.frame_count),
        "--row-padding-bytes",
        "4",
        "--depth-bigendian",
    )
    _run_python("convert_to_vrs.py", str(bag_path), str(vrs_path), "--imu", "--compression", "none")
    _check_vrs_against_bag(bag_path, vrs_path, spec)


def test_synthetic_pixels_follow_documented_pattern(tmp_path: Path) -> None:
    """Ensure the generator itself creates changing, non-trivial sample values."""
    spec = SyntheticBagSpec(width=8, height=6, frame_count=2)
    bag_path = write_synthetic_rosbag(tmp_path / "pattern.bag", spec)
    messages = _read_input_bag(bag_path)
    for index in range(spec.frame_count):
        color = _image_from_ros_message(messages[_DATA_TOPICS[1001]][index][1])
        depth = _image_from_ros_message(messages[_DATA_TOPICS[1002]][index][1])
        # Independent scalar examples guard against constant/empty fixture data.
        np.testing.assert_array_equal(color[2, 3], [3 + 7 * index, 2 + 11 * index, 5 + 13 * index])
        assert int(depth[2, 3]) == 127 + 101 * index
        assert int(depth[0, 0]) == 0
        assert int(depth[-1, -1]) == 65535
    original = bag_path.read_bytes()
    with pytest.raises(FileExistsError, match="overwrite"):
        write_synthetic_rosbag(bag_path, spec)
    assert bag_path.read_bytes() == original


@pytest.mark.parametrize(
    "kwargs",
    [{"frame_count": 0}, {"width": -1}, {"depth_scale": float("nan")}, {"row_padding_bytes": -1}],
)
def test_synthetic_spec_rejects_invalid_inputs(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        SyntheticBagSpec(**kwargs)
