"""Regression tests for the converter-facing writer API and schema reader."""

from __future__ import annotations

import struct
from pathlib import Path

from scripts.vrs_reader import VRSReader
from scripts.vrs_writer import VRSWriter


def test_vrs_writer_adapter_preserves_existing_api(tmp_path: Path) -> None:
    """The converter API accepts valid image bytes and closes idempotently."""
    output_vrs = tmp_path / "adapter_api.vrs"
    writer = VRSWriter(output_vrs)
    assert writer.is_open()
    writer.add_stream(1001, "RealSense_D435i_Color")
    writer.write_configuration(1001, {"width": 2, "height": 2, "encoding": "rgb8"})
    writer.write_data(1001, 0.0, bytes(range(12)))
    writer.close()
    writer.close()
    assert not writer.is_open()


def test_vrs_writer_adapter_writes_readable_records(tmp_path: Path) -> None:
    """The repository reader reconstructs image, IMU and opaque bytes exactly."""
    output_vrs = tmp_path / "adapter_roundtrip.vrs"
    payloads = {
        1001: bytes(range(12)),
        1003: struct.pack("<ddd", 0.125, -0.5, 9.80665),
        2001: b"\x00\xffopaque\x80bytes",
    }
    with VRSWriter(output_vrs, flush_bytes=1) as writer:
        for stream_id in payloads:
            writer.add_stream(stream_id, f"synthetic-{stream_id}")
        writer.write_configuration(1001, {"width": 2, "height": 2, "encoding": "rgb8"})
        writer.write_configuration(1003, {"sensor_type": "accelerometer"})
        for stream_id, payload in payloads.items():
            writer.write_data(stream_id, 0.125, payload)

    with VRSReader(output_vrs) as reader:
        assert reader.get_stream_ids() == list(payloads)
        assert reader.read_configuration(1001)["encoding"] == "rgb8"
        for stream_id, payload in payloads.items():
            records = list(reader.read_data_records(stream_id))
            assert records == [{"timestamp": 0.125, "data": payload}]
