"""Real synthetic bag/CLI/VRS tests and independent restoration of encoded images."""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import zlib
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import pytest
import pyvrs
from rosbags.highlevel import AnyReader

from scripts.image_codec_storage import CODEC_IMAGE, IMAGE_CODEC_TAG
from scripts.image_codecs import (
    CodecRegistry,
    CodecSpec,
    ImageCodecError,
    default_codec_registry,
)
from scripts.synthetic_rosbag import SyntheticBagSpec, write_synthetic_rosbag
from scripts.vrs_reader import VRSReader
from scripts.vrs_writer import VRSWriter

_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(bag, vrs, *options):
    return subprocess.run(
        [sys.executable, "convert_to_vrs.py", str(bag), str(vrs), *options],
        cwd=_ROOT, capture_output=True, text=True, timeout=60, check=False,
    )


def _original_images(bag):
    result = defaultdict(list)
    with AnyReader([bag]) as reader:
        for connection, timestamp, rawdata in reader.messages():
            if not connection.topic.endswith("/image/data"):
                continue
            msg = reader.deserialize(rawdata, connection.msgtype)
            color = "/Color_" in connection.topic
            row_bytes = msg.width * (3 if color else 2)
            rows = np.asarray(msg.data, dtype=np.uint8).reshape(msg.height, msg.step)
            packed = rows[:, :row_bytes].copy().tobytes()
            dtype = np.uint8 if color else np.dtype(">u2" if msg.is_bigendian else "<u2")
            shape = (msg.height, msg.width, 3) if color else (msg.height, msg.width)
            image = np.frombuffer(packed, dtype=dtype).reshape(shape)
            result[1001 if color else 1002].append((timestamp / 1e9, image))
    return result


def _independent_read(vrs, expected, color_codec, depth_codec):
    """Use official reader + standard codec library, never our production decoder."""
    counts = defaultdict(int)
    reader = pyvrs.SyncVRSReader(str(vrs))
    reader.set_image_conversion(pyvrs.ImageConversion.OFF)
    try:
        for record in reader:
            if record.record_type != "data":
                continue
            tags = reader.stream_tags[record.stream_id]
            stream = int(tags["user_stream_id"])
            if stream not in (1001, 1002):
                continue
            timestamp, original = expected[stream][counts[stream]]
            assert record.timestamp == pytest.approx(timestamp, rel=0, abs=1e-9)
            codec = color_codec if stream == 1001 else depth_codec
            if codec == "raw":
                assert tags["vrs_sandbox_schema_version"] == "2"
                assert tags["payload_encoding"] == "native_image"
                assert record.n_image_blocks == 1
                restored = np.asarray(record.image_blocks[0])
            else:
                assert tags["vrs_sandbox_schema_version"] == "3"
                assert tags["payload_encoding"] == CODEC_IMAGE
                assert record.n_image_blocks == 0  # Compressed bytes must not masquerade as RAW.
                descriptor = json.loads(tags[IMAGE_CODEC_TAG])
                assert descriptor["codec"]["name"] == codec
                assert descriptor["codec"]["version"] == 1
                assert descriptor["lossless"] == (codec != "jpeg")
                payload = base64.b64decode(record.metadata_blocks[0]["some_string"], validate=True)
                assert payload.startswith(b"\x89PNG" if codec == "png" else b"\xff\xd8")
                restored = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
                assert restored is not None
                if stream == 1001:
                    restored = cv2.cvtColor(restored, cv2.COLOR_BGR2RGB)
                if codec == "jpeg":
                    assert descriptor["codec"]["options"] == {"quality": 90}
            assert restored.shape == original.shape
            assert restored.dtype.kind == original.dtype.kind
            assert restored.dtype.itemsize == original.dtype.itemsize
            if codec == "jpeg":
                # A fixture-specific quality bound, not a codec-wide accuracy guarantee.
                assert np.abs(restored.astype(float) - original).mean() < 6
            else:
                np.testing.assert_array_equal(restored, original)
            counts[stream] += 1
    finally:
        reader.close()
    assert dict(counts) == {stream: len(samples) for stream, samples in expected.items()}


@pytest.mark.e2e
@pytest.mark.parametrize("record_compression", ["none", "lz4", "zstd"])
@pytest.mark.parametrize("color_codec,depth_codec", [
    ("raw", "raw"), ("png", "png"), ("jpeg", "png"),
    ("png", "raw"), ("raw", "png"), ("jpeg", "raw"),
])
def test_independent_codecs_real_bag_cli_official_reader(
    tmp_path, record_compression, color_codec, depth_codec
):
    spec = SyntheticBagSpec(frame_count=3)
    bag = write_synthetic_rosbag(tmp_path / "images.bag", spec)
    output = tmp_path / "images.vrs"
    options = [
        "--imu", "--compression", record_compression,
        "--color-codec", color_codec, "--depth-codec", depth_codec,
    ]
    if color_codec == "jpeg":
        options += ["--color-codec-options", '{"quality":90}']
    if depth_codec == "png":
        options += ["--depth-codec-options", '{"compression_level":1}']
    result = _run_cli(bag, output, *options)
    assert result.returncode == 0, result.stdout + result.stderr
    expected = _original_images(bag)
    _independent_read(output, expected, color_codec, depth_codec)
    # The existing consumer API must return restored pixel bytes, not JPEG/PNG bytes.
    with VRSReader(output) as reader:
        for stream, codec in ((1001, color_codec), (1002, depth_codec)):
            samples = list(reader.read_data_records(stream))
            assert len(samples) == spec.frame_count
            for sample, (timestamp, original) in zip(samples, expected[stream]):
                assert sample["timestamp"] == pytest.approx(timestamp)
                restored = np.frombuffer(sample["data"], dtype="u1" if stream == 1001 else "<u2")
                restored = restored.reshape(original.shape)
                if codec == "jpeg":
                    assert np.abs(restored.astype(float) - original).mean() < 6
                else:
                    np.testing.assert_array_equal(restored, original)
            if codec != "raw":
                encoded = list(reader.read_encoded_image_records(stream))
                assert len(encoded) == spec.frame_count
                assert encoded[0]["descriptor"].codec.name == codec
        assert reader.read_configuration(1002)["depth_scale"] == spec.depth_scale
        assert reader.get_record_count(1003) == spec.frame_count
        assert reader.get_record_count(1004) == spec.frame_count


@pytest.mark.e2e
def test_png_real_bag_normalizes_row_padding_and_big_endian(tmp_path):
    spec = SyntheticBagSpec(width=8, height=6, frame_count=2, row_padding_bytes=4, depth_bigendian=True)
    bag = write_synthetic_rosbag(tmp_path / "padded.bag", spec)
    output = tmp_path / "padded.vrs"
    result = _run_cli(bag, output, "--color-codec", "png", "--depth-codec", "png")
    assert result.returncode == 0, result.stdout + result.stderr
    _independent_read(output, _original_images(bag), "png", "png")


@pytest.mark.parametrize("options", [
    ["--depth-codec", "jpeg"],
    ["--color-codec", "png", "--color-codec-options", '{"quality":90}'],
    ["--color-codec-options", "[]"],
    ["--depth-codec", "png", "--depth-codec-options", '{"compression_level":99}'],
])
def test_bad_cli_options_fail_without_output(tmp_path, options):
    bag = write_synthetic_rosbag(tmp_path / "invalid.bag", SyntheticBagSpec(width=8, height=6))
    output = tmp_path / "invalid.vrs"
    result = _run_cli(bag, output, *options)
    assert result.returncode != 0
    assert not output.exists()


class _DepthEncoder:
    """Test-only depth extension; not a new production compression format."""

    def __init__(self, codec):
        assert codec.options == {"level": 1}

    def validate(self, image):
        if image.role != "depth":
            raise ImageCodecError("This example is only for depth")

    def encode(self, pixels, image):
        return b"TEST-DEPTH-1\0" + zlib.compress(pixels.tobytes(), level=1)


class _IndependentDepthDecoder:
    def __init__(self, codec):
        pass

    def validate(self, image):
        if image.role != "depth":
            raise ImageCodecError("This example is only for depth")

    def decode(self, payload, image):
        if not payload.startswith(b"TEST-DEPTH-1\0"):
            raise ImageCodecError("Invalid example depth header")
        return image.array_from_bytes(zlib.decompress(payload[len(b"TEST-DEPTH-1\0"): ]))


@pytest.mark.parametrize("encoding", ["16UC1", "32FC1"])
def test_injected_depth_encoder_and_separate_decoder_roundtrip(tmp_path, encoding):
    output = tmp_path / "plugin.vrs"
    spec = CodecSpec("test-depth-zlib", options={"level": 1})
    encoders = default_codec_registry()
    encoders.register_encoder("test-depth-zlib", 1, _DepthEncoder, lossless=True)
    config = {"width": 3, "height": 2, "encoding": encoding, "depth_scale": 0.002}
    if encoding == "16UC1":
        pixels = np.array([0, 1, 255, 256, 12345, 65535], dtype="<u2").reshape(2, 3)
    else:
        bits = np.array([0, 0x80000000, 0x7FC00001, 0x7F800000, 0xFF800000, 0x3F800000], dtype="<u4")
        pixels = bits.view("<f4").reshape(2, 3)
    with VRSWriter(output, image_codecs={1002: spec}, codec_registry=encoders, flush_records=1) as writer:
        writer.add_stream(1002, "depth")
        writer.write_configuration(1002, config)
        for timestamp in (0.0, 0.0, 1.0):
            writer.write_data(1002, timestamp, pixels.tobytes())
    with VRSReader(output) as reader:
        with pytest.raises(ImageCodecError, match="Unsupported image decoder"):
            list(reader.read_data_records(1002))
        # Compressed extraction does not require installing an unknown decoder.
        assert len(list(reader.read_encoded_image_records(1002))) == 3
    decoders = CodecRegistry()
    decoders.register_decoder("test-depth-zlib", 1, _IndependentDepthDecoder)
    with VRSReader(output, codec_registry=decoders) as reader:
        records = list(reader.read_data_records(1002))
        assert [record["timestamp"] for record in records] == [0.0, 0.0, 1.0]
        assert all(record["data"] == pixels.tobytes() for record in records)
        assert reader.read_configuration(1002) == config


def test_unknown_codec_and_nonimage_selection_fail_before_create(tmp_path):
    output = tmp_path / "invalid.vrs"
    with pytest.raises(ImageCodecError, match="Unsupported image encoder"):
        with VRSWriter(output, image_codecs={1001: CodecSpec("missing")}) as writer:
            writer.add_stream(1001, "color")
            writer.write_configuration(1001, {"width": 8, "height": 6, "encoding": "rgb8"})
    assert not output.exists()
    with pytest.raises(ValueError, match="non-image"):
        with VRSWriter(output, image_codecs={1003: CodecSpec("png")}) as writer:
            writer.add_stream(1003, "imu")
            writer.write_configuration(1003, {"sensor_type": "accelerometer"})
    assert not output.exists()
