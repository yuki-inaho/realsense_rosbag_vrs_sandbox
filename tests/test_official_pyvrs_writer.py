"""Regression tests for the official PyVRS writer API."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _find_official_writer() -> tuple[str, type[Any]]:
    """Return the first supported official PyVRS writer class."""
    from scripts.vrs_writer import load_official_writer_backend

    import_path, writer_cls, _pyvrs = load_official_writer_backend()
    return import_path, writer_cls


def test_official_vrs_writer_imports() -> None:
    """The official PyVRS writer must be importable from one known path."""
    import_path, writer_cls = _find_official_writer()

    assert import_path
    assert callable(writer_cls)


def test_official_vrs_writer_roundtrip_color_depth_imu(tmp_path: Path) -> None:
    """Official writer must support a minimal color/depth/IMU roundtrip."""
    import_path, _writer_cls = _find_official_writer()

    output_vrs = tmp_path / "official_writer_roundtrip.vrs"
    from scripts.vrs_writer import VRSWriter

    writer = VRSWriter(str(output_vrs), compression="none")
    assert writer.backend_name == import_path

    assert hasattr(writer, "add_stream"), f"{import_path} has no add_stream API"
    assert hasattr(writer, "write_configuration"), f"{import_path} has no write_configuration API"
    assert hasattr(writer, "write_data"), f"{import_path} has no write_data API"

    writer.add_stream(1001, "RealSense_D435i_Color|id:1001")
    writer.add_stream(1002, "RealSense_D435i_Depth|id:1002")
    writer.add_stream(1003, "RealSense_D435i_Accel|id:1003")
    writer.add_stream(1004, "RealSense_D435i_Gyro|id:1004")
    writer.write_configuration(1001, {"width": 2, "height": 2, "encoding": "rgb8"})
    writer.write_configuration(1002, {"width": 2, "height": 2, "encoding": "16UC1"})
    writer.write_configuration(1003, {"sensor_type": "accelerometer"})
    writer.write_configuration(1004, {"sensor_type": "gyroscope"})
    writer.write_data(1001, 0.0, bytes(range(12)))
    writer.write_data(1002, 0.0, bytes(range(8)))
    writer.write_data(1003, 0.0, bytes(24))
    writer.write_data(1004, 0.0, bytes(24))
    if hasattr(writer, "close"):
        writer.close()

    from scripts.vrs_reader import VRSReader

    with VRSReader(output_vrs) as reader:
        assert reader.get_stream_ids() == [1001, 1002, 1003, 1004]
        assert reader.read_configuration(1001)["encoding"] == "rgb8"
        assert reader.get_record_count(1001) == 1
        assert reader.get_record_count(1002) == 1
        assert reader.get_record_count(1003) == 1
        assert reader.get_record_count(1004) == 1
