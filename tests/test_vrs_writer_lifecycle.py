"""Boundary, buffering and failure tests for the official VRS writer."""

from __future__ import annotations

import base64
import math
from pathlib import Path
from typing import Any

import pytest

from scripts.vrs_writer import VRSWriter


def _opaque_records(path: Path) -> list[tuple[float, bytes]]:
    """Read opaque payloads independently of the repository's reader."""
    import pyvrs

    reader = pyvrs.SyncVRSReader(path)
    try:
        return [
            (
                record.timestamp,
                base64.b64decode(record.metadata_blocks[0]["some_string"], validate=True),
            )
            for record in reader
            if record.record_type == "data"
        ]
    finally:
        reader.close()


@pytest.mark.parametrize("limits", [{"flush_records": 1}, {"flush_bytes": 1}, {}])
def test_equal_timestamps_variable_lengths_and_final_record_are_preserved(
    tmp_path: Path, limits: dict[str, int]
) -> None:
    """Every byte survives flush boundaries, including the final equal timestamp."""
    path = tmp_path / "equal-timestamps.vrs"
    expected = [(0.0, b"\x00"), (0.0, bytes(range(256))), (0.125, b"last"), (0.125, b"tail")]
    with VRSWriter(path, **limits) as writer:
        writer.add_stream(1, "opaque")
        for timestamp, payload in expected:
            writer.write_data(1, timestamp, list(payload))
    assert _opaque_records(path) == expected


@pytest.mark.parametrize(
    ("limits", "minimum_flushes"),
    [({"flush_records": 2}, 2), ({"flush_bytes": 8}, 5)],
)
def test_pending_batches_are_written_before_close(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    limits: dict[str, int],
    minimum_flushes: int,
) -> None:
    """Observe actual native writes during a recording, not only at final close."""
    import scripts.vrs_writer as module

    name, native_cls, bindings = module.load_official_writer_backend()
    flush_timestamps = []

    class ObservedWriter:
        def __init__(self) -> None:
            self.native = native_cls()

        def __getattr__(self, attribute: str) -> Any:
            return getattr(self.native, attribute)

        def writeRecords(self, timestamp: float) -> int:  # noqa: N802
            flush_timestamps.append(timestamp)
            return self.native.writeRecords(timestamp)

    monkeypatch.setattr(
        module, "load_official_writer_backend", lambda: (name, ObservedWriter, bindings)
    )
    path = tmp_path / "periodic.vrs"
    expected = [(index / 30.0, bytes([index]) * 4) for index in range(5)]
    with VRSWriter(path, **limits) as writer:
        writer.add_stream(1, "opaque")
        for timestamp, payload in expected:
            writer.write_data(1, timestamp, payload)
        assert len(flush_timestamps) >= minimum_flushes
    assert _opaque_records(path) == expected


@pytest.mark.parametrize("timestamp", [-1.0, math.nan, math.inf, -math.inf, True])
def test_invalid_timestamps_are_rejected_without_poisoning_writer(
    tmp_path: Path, timestamp: float
) -> None:
    path = tmp_path / "valid-after-rejection.vrs"
    with VRSWriter(path) as writer:
        writer.add_stream(1, "opaque")
        with pytest.raises(ValueError, match="finite non-negative"):
            writer.write_data(1, timestamp, b"invalid")
        writer.write_data(1, 0.0, b"valid")
    assert _opaque_records(path) == [(0.0, b"valid")]


def test_out_of_order_data_and_late_setup_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "frozen.vrs"
    with VRSWriter(path, flush_records=1) as writer:
        writer.add_stream(1, "first")
        writer.add_stream(2, "second")
        writer.write_data(1, 2.0, b"first")
        with pytest.raises(ValueError, match="nondecreasing"):
            writer.write_data(2, 1.0, b"late")
        with pytest.raises(RuntimeError, match="fixed"):
            writer.add_stream(3, "too late")
        with pytest.raises(RuntimeError, match="fixed"):
            writer.write_configuration(2, {"value": "too late"})
        writer.write_data(2, 2.0, b"same time")
    assert _opaque_records(path) == [(2.0, b"first"), (2.0, b"same time")]


@pytest.mark.parametrize(
    ("configuration", "invalid_payload", "valid_payload"),
    [
        ({"width": 2, "height": 2, "encoding": "rgb8"}, b"rgb", bytes(12)),
        ({"width": 2, "height": 2, "encoding": "16UC1"}, bytes(7), bytes(8)),
        ({"sensor_type": "accelerometer"}, bytes(23), bytes(24)),
    ],
)
def test_typed_payload_lengths_are_enforced(
    tmp_path: Path,
    configuration: dict[str, Any],
    invalid_payload: bytes,
    valid_payload: bytes,
) -> None:
    with VRSWriter(tmp_path / "typed.vrs") as writer:
        writer.add_stream(1, "typed")
        writer.write_configuration(1, configuration)
        with pytest.raises(ValueError, match="payload"):
            writer.write_data(1, 0.0, invalid_payload)
        writer.write_data(1, 0.0, valid_payload)


def test_configuration_is_snapshotted_before_the_caller_mutates_it(tmp_path: Path) -> None:
    import json

    import pyvrs

    path = tmp_path / "snapshot.vrs"
    configuration = {"width": 1, "height": 1, "encoding": "rgb8", "camera_k": [1.0]}
    with VRSWriter(path) as writer:
        writer.add_stream(1, "camera")
        writer.write_configuration(1, configuration)
        configuration["width"] = 200
        configuration["camera_k"][0] = 5.0
        writer.write_data(1, 0.0, b"rgb")
    reader = pyvrs.SyncVRSReader(path)
    try:
        saved = json.loads(next(iter(reader.stream_tags.values()))["config_json"])
        assert saved["width"] == 1
        assert saved["camera_k"] == [1.0]
    finally:
        reader.close()


def test_invalid_output_path_closes_failed_writer(tmp_path: Path) -> None:
    parent_file = tmp_path / "not-a-directory"
    parent_file.write_text("not a directory")
    writer = VRSWriter(parent_file / "output.vrs")
    writer.add_stream(1, "opaque")
    with pytest.raises((RuntimeError, OSError)):
        writer.write_data(1, 0.0, b"data")
    assert not writer.is_open()
    writer.close()


@pytest.mark.parametrize("failed_operation", ["create", "writeRecords", "close"])
def test_official_error_status_is_reported_and_native_writer_is_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_operation: str
) -> None:
    """Inject an I/O status at the official boundary while using real VRS otherwise."""
    import scripts.vrs_writer as module

    name, native_cls, bindings = module.load_official_writer_backend()
    instances = []

    class StatusWriter:
        def __init__(self) -> None:
            self.native = native_cls()
            self.close_calls = 0
            instances.append(self)

        def __getattr__(self, attribute: str) -> Any:
            return getattr(self.native, attribute)

        def create(self, path: str) -> int:
            result = self.native.create(path)
            return 37 if failed_operation == "create" else result

        def writeRecords(self, timestamp: float) -> int:  # noqa: N802
            result = self.native.writeRecords(timestamp)
            return 37 if failed_operation == "writeRecords" else result

        def close(self) -> int:
            self.close_calls += 1
            result = self.native.close()
            return 37 if failed_operation == "close" else result

    monkeypatch.setattr(
        module, "load_official_writer_backend", lambda: (name, StatusWriter, bindings)
    )
    writer = VRSWriter(tmp_path / "fault.vrs", flush_records=1)
    writer.add_stream(1, "opaque")
    with pytest.raises(RuntimeError, match=f"{failed_operation} failed"):
        writer.write_data(1, 0.0, b"data")
        writer.close()
    assert not writer.is_open()
    writer.close()
    assert instances[0].close_calls == 1
