"""Integration tests that require a user-provided RealSense ROSbag."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.rosbag_to_vrs_converter import RosbagToVRSConverter, create_rgbd_config
from scripts.vrs_reader import VRSReader


@pytest.mark.integration
def test_real_rosbag_conversion_when_env_is_set(tmp_path: Path) -> None:
    """Run real conversion only when REALSENSE_ROSBAG_PATH is explicitly set."""
    rosbag_env = os.environ.get("REALSENSE_ROSBAG_PATH")
    if not rosbag_env:
        pytest.skip("REALSENSE_ROSBAG_PATH is not set")

    rosbag_path = Path(rosbag_env)
    if not rosbag_path.exists():
        raise FileNotFoundError(f"REALSENSE_ROSBAG_PATH does not exist: {rosbag_path}")

    output_vrs = tmp_path / "real_rosbag.vrs"
    converter = RosbagToVRSConverter(rosbag_path, output_vrs, create_rgbd_config())
    result = converter.convert()

    assert output_vrs.exists()
    assert output_vrs.stat().st_size > 0
    assert result.total_messages > 0

    with VRSReader(output_vrs) as reader:
        stream_ids = reader.get_stream_ids()

    assert 1001 in stream_ids
    assert 1002 in stream_ids
