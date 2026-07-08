"""Regression tests for the repository VRS writer adapter."""

from __future__ import annotations

from pathlib import Path


def test_vrs_writer_adapter_preserves_existing_api(tmp_path: Path) -> None:
    """The adapter must keep the existing converter-facing writer API."""
    from scripts.vrs_writer import VRSWriter

    output_vrs = tmp_path / "adapter_api.vrs"
    writer = VRSWriter(output_vrs)

    assert writer.is_open()
    writer.add_stream(1001, "RealSense_D435i_Color")
    writer.write_configuration(1001, {"width": 2, "height": 2, "encoding": "rgb8"})
    writer.write_data(1001, 0.0, b"\x00\x01\x02")
    writer.close()
    assert not writer.is_open()


def test_vrs_writer_adapter_writes_readable_records(tmp_path: Path) -> None:
    """Records written through the adapter must be readable by the repo reader."""
    from scripts.vrs_reader import VRSReader
    from scripts.vrs_writer import VRSWriter

    output_vrs = tmp_path / "adapter_roundtrip.vrs"
    with VRSWriter(output_vrs) as writer:
        writer.add_stream(1001, "RealSense_D435i_Color")
        writer.write_configuration(1001, {"width": 2, "height": 2, "encoding": "rgb8"})
        writer.write_data(1001, 0.125, b"rgb")

    with VRSReader(output_vrs) as reader:
        assert reader.get_stream_ids() == [1001]
        assert reader.read_configuration(1001)["encoding"] == "rgb8"
        records = list(reader.read_data_records(1001))

    assert len(records) == 1
    assert records[0]["timestamp"] == 0.125
    assert records[0]["data"] == b"rgb"
