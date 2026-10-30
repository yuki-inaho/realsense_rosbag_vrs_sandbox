"""Check the written format with the unmodified official PyVRS reader."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np
import pytest

from scripts.vrs_schema import (
    CONFIG_JSON_TAG,
    IMU_VECTOR,
    NATIVE_IMAGE,
    PAYLOAD_ENCODING_TAG,
    SCHEMA_VERSION,
    SCHEMA_VERSION_TAG,
    USER_STREAM_ID_TAG,
)
from scripts.vrs_writer import VRSWriter, load_official_writer_backend


def test_official_backend_does_not_patch_pyvrs() -> None:
    """The official native writer needs no missing-export or enum monkeypatch."""
    import pyvrs
    import vrsbindings

    symbols = ("RecordFormat", "Stream", "Writer")
    before = {name: getattr(pyvrs, name, None) for name in symbols}
    compression_alias = getattr(pyvrs.CompressionPreset, "Zmedium", None)
    import_path, writer_cls, bindings = load_official_writer_backend()

    assert import_path == "vrsbindings.Writer"
    assert writer_cls is vrsbindings.Writer
    assert bindings is vrsbindings
    assert before == {name: getattr(pyvrs, name, None) for name in symbols}
    assert getattr(pyvrs.CompressionPreset, "Zmedium", None) is compression_alias


@pytest.mark.parametrize("compression", ["none", "lz4", "zstd"])
def test_official_reader_sees_real_images_and_typed_imu(tmp_path: Path, compression: str) -> None:
    """RGB/depth shapes, all pixels, and IMU values survive repeated native flushes."""
    import pyvrs

    color = np.arange(36, dtype=np.uint8).reshape(3, 4, 3)
    depth = np.array([[0, 1, 255, 256], [257, 1000, 32768, 65535], [2, 3, 4, 5]], dtype="<u2")
    accel = (0.125, -0.25, 9.80665)
    gyro = (-1.0, 0.0, 1.5)
    config = {
        1001: {"width": 4, "height": 3, "encoding": "rgb8", "camera_k": [1.0] * 9},
        1002: {"width": 4, "height": 3, "encoding": "16UC1", "depth_scale": 0.001},
        1003: {"sensor_type": "accelerometer"},
        1004: {"sensor_type": "gyroscope"},
        2001: {"serial_number": "synthetic-only"},
    }
    path = tmp_path / "native_types.vrs"
    with VRSWriter(path, compression=compression, flush_records=1) as writer:
        for stream_id, configuration in config.items():
            writer.add_stream(stream_id, f"synthetic-{stream_id}")
            writer.write_configuration(stream_id, configuration)
        for timestamp in (0.0, 0.033):
            writer.write_data(1001, timestamp, color.tobytes())
            writer.write_data(1002, timestamp, depth.tobytes())
            writer.write_data(1003, timestamp, struct.pack("<ddd", *accel))
            writer.write_data(1004, timestamp, struct.pack("<ddd", *gyro))

    reader = pyvrs.SyncVRSReader(path)
    reader.set_image_conversion(pyvrs.ImageConversion.OFF)
    counts = dict.fromkeys(config, 0)
    configuration_ids = set()
    try:
        for tags in reader.stream_tags.values():
            assert tags[SCHEMA_VERSION_TAG] == SCHEMA_VERSION
            logical_id = int(tags[USER_STREAM_ID_TAG])
            assert json.loads(tags[CONFIG_JSON_TAG]) == config[logical_id]
        for record in reader:
            tags = reader.stream_tags[record.stream_id]
            logical_id = int(tags[USER_STREAM_ID_TAG])
            if record.record_type == "configuration":
                configuration_ids.add(logical_id)
                continue
            if record.record_type != "data":
                continue
            assert record.timestamp == (0.0, 0.033)[counts[logical_id]]
            counts[logical_id] += 1
            if logical_id in (1001, 1002):
                assert tags[PAYLOAD_ENCODING_TAG] == NATIVE_IMAGE
                expected = color if logical_id == 1001 else depth
                image = np.asarray(record.image_blocks[0])
                assert image.shape == expected.shape
                assert image.dtype == expected.dtype
                np.testing.assert_array_equal(image, expected)
            else:
                assert tags[PAYLOAD_ENCODING_TAG] == IMU_VECTOR
                assert record.n_image_blocks == 0
                expected_vector = accel if logical_id == 1003 else gyro
                assert record.metadata_blocks[0]["doubles"] == list(expected_vector)
    finally:
        reader.close()
    assert configuration_ids == set(config)
    assert counts == {1001: 2, 1002: 2, 1003: 2, 1004: 2, 2001: 0}
