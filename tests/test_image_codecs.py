"""Codec contract tests independent of ROS, VRS, and hardware."""

from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
import pytest

from scripts.image_codec_storage import decode_payload_text, encode_payload_text
from scripts.image_codecs import (
    CodecRegistry,
    CodecSpec,
    ImageCodecDescriptor,
    ImageCodecError,
    ImageSpec,
    decode_pixels,
    default_codec_registry,
    encode_pixels,
)


def _pixels(spec: ImageSpec):
    data = np.arange(np.prod(spec.shape), dtype=np.uint32).reshape(spec.shape)
    result = (data * 73 % 65536).astype(spec.dtype)
    if spec.encoding in ("16UC1", "mono16"):
        result.flat[0], result.flat[-1] = 0, 65535
    return result


@pytest.mark.parametrize("name", ["raw", "png"])
@pytest.mark.parametrize("encoding", ["rgb8", "bgr8", "rgba8", "mono8", "8UC1", "mono16", "16UC1"])
def test_lossless_all_pixels_channels_types_and_extremes(name, encoding):
    spec = ImageSpec(17, 13, encoding)
    registry, codec = default_codec_registry(), CodecSpec(name)
    encoder, lossless = registry.encoder(codec, spec)
    pixels = _pixels(spec)
    original = pixels.copy()
    payload = encode_pixels(encoder, pixels, spec)
    restored = decode_pixels(registry.decoder(codec, spec), payload, spec)
    assert lossless
    assert restored.dtype == np.dtype(spec.dtype)
    np.testing.assert_array_equal(restored, pixels)
    np.testing.assert_array_equal(pixels, original)


def test_raw_float_depth_preserves_nan_inf_signed_zero_bits():
    spec = ImageSpec(3, 2, "32FC1", "depth")
    bits = np.array([0, 0x80000000, 0x7FC00001, 0x7F800000, 0xFF800000, 0x3F800000], dtype="<u4")
    pixels = bits.view("<f4").reshape(spec.shape)
    registry, codec = default_codec_registry(), CodecSpec()
    encoder, _ = registry.encoder(codec, spec)
    restored = decode_pixels(registry.decoder(codec, spec), encode_pixels(encoder, pixels, spec), spec)
    assert restored.tobytes() == pixels.tobytes()


@pytest.mark.parametrize("encoding", ["rgb8", "bgr8", "mono8"])
def test_jpeg_is_explicitly_lossy_with_bounded_fixture_error(encoding):
    spec = ImageSpec(96, 64, encoding)
    y, x = np.indices((64, 96))
    rgb = np.stack([x + 20, y + 40, (x + y) // 2 + 120], axis=-1).astype(np.uint8)
    pixels = rgb if spec.channels == 3 else rgb[..., 0]
    registry, codec = default_codec_registry(), CodecSpec("jpeg", options={"quality": 95})
    encoder, lossless = registry.encoder(codec, spec)
    payload = encode_pixels(encoder, pixels, spec)
    restored = decode_pixels(registry.decoder(codec, spec), payload, spec)
    assert not lossless
    assert payload.startswith(b"\xff\xd8")
    assert np.abs(restored.astype(float) - pixels).mean() < 3


@pytest.mark.parametrize("name,encoding,role", [
    ("jpeg", "16UC1", "depth"), ("jpeg", "32FC1", "depth"),
    ("jpeg", "mono8", "depth"), ("jpeg", "rgba8", "color"),
    ("png", "32FC1", "depth"),
])
def test_no_implicit_depth_quantization_or_alpha_loss(name, encoding, role):
    with pytest.raises(ImageCodecError):
        default_codec_registry().encoder(CodecSpec(name), ImageSpec(8, 6, encoding, role))


@pytest.mark.parametrize("name,options", [
    ("raw", {"quality": 95}), ("png", {"quality": 95}),
    ("png", {"compression_level": 10}), ("png", {"compression_level": True}),
    ("jpeg", {"quality": 0}), ("jpeg", {"quality": 101}), ("jpeg", {"quality": 90.0}),
])
def test_invalid_codec_options_fail(name, options):
    with pytest.raises(ImageCodecError):
        default_codec_registry().encoder(CodecSpec(name, options=options), ImageSpec(8, 6, "rgb8"))


def test_specs_are_immutable_snapshots_and_roundtrip_json():
    options = {"quality": 90}
    codec = CodecSpec("jpeg", options=options)
    options["quality"] = 1
    descriptor = ImageCodecDescriptor(ImageSpec(8, 6, "rgb8"), codec, False)
    assert ImageCodecDescriptor.from_json(descriptor.to_json()) == descriptor
    assert codec.options["quality"] == 90
    with pytest.raises(TypeError):
        codec.options["quality"] = 20


@pytest.mark.parametrize("change", [
    {"descriptor_version": 2}, {"descriptor_version": True},
    {"lossless": "false"}, {"codec": {"name": "png", "version": 1}}, {"image": []},
])
def test_invalid_descriptor(change):
    value = json.loads(ImageCodecDescriptor(ImageSpec(8, 6, "rgb8"), CodecSpec("png"), True).to_json())
    value.update(change)
    with pytest.raises(ImageCodecError):
        ImageCodecDescriptor.from_json(json.dumps(value))


@pytest.mark.parametrize("name", ["png", "jpeg"])
def test_wrong_dimensions_rejected_before_native_decode(name, monkeypatch):
    import cv2

    spec = ImageSpec(16, 12, "rgb8")
    registry, codec = default_codec_registry(), CodecSpec(name)
    encoder, _ = registry.encoder(codec, spec)
    payload = encode_pixels(encoder, _pixels(spec), spec)
    wrong_spec = replace(spec, width=17)
    monkeypatch.setattr(cv2, "imdecode", lambda *args: pytest.fail("must reject before allocation"))
    with pytest.raises(ImageCodecError, match="dimensions"):
        decode_pixels(registry.decoder(codec, wrong_spec), payload, wrong_spec)


@pytest.mark.parametrize("name,payload", [("png", b"bad"), ("jpeg", b"bad"), ("jpeg", b"\xff\xd8")])
def test_corrupt_payloads_rejected(name, payload):
    spec = ImageSpec(8, 6, "rgb8")
    with pytest.raises(ImageCodecError):
        decode_pixels(default_codec_registry().decoder(CodecSpec(name), spec), payload, spec)


def test_codec_does_not_silently_decode_another_format():
    spec, registry = ImageSpec(8, 6, "rgb8"), default_codec_registry()
    encoder, _ = registry.encoder(CodecSpec("png"), spec)
    payload = encode_pixels(encoder, _pixels(spec), spec)
    with pytest.raises(ImageCodecError, match="JPEG"):
        decode_pixels(registry.decoder(CodecSpec("jpeg"), spec), payload, spec)


@pytest.mark.parametrize("text", ["", "not base64!", "////=oops", None, 3])
def test_invalid_carrier_text(text):
    with pytest.raises(ImageCodecError):
        decode_payload_text(text)


def test_carrier_does_not_change_compressed_bytes():
    payload = bytes(range(256))
    assert decode_payload_text(encode_payload_text(payload)) == payload


def test_no_unknown_codec_fallback_and_no_registry_global_state():
    registry = default_codec_registry()
    spec = ImageSpec(8, 6, "rgb8")
    for codec in (CodecSpec("unknown"), CodecSpec("png", 999)):
        with pytest.raises(ImageCodecError, match="Unsupported"):
            registry.encoder(codec, spec)
        with pytest.raises(ImageCodecError, match="Unsupported"):
            registry.decoder(codec, spec)
    with pytest.raises(ImageCodecError, match="already registered"):
        registry.register_decoder("png", 1, lambda codec: None)
    blank = CodecRegistry()
    snapshot = blank.copy()
    blank.register_decoder("example", 1, lambda codec: None)
    with pytest.raises(ImageCodecError):
        snapshot.decoder(CodecSpec("example"), spec)


@pytest.mark.parametrize("kwargs", [
    {"width": True}, {"width": 0}, {"width": 1 << 31}, {"encoding": "bad"}, {"role": "bad"},
])
def test_invalid_image_specs(kwargs):
    fields = {"width": 8, "height": 6, "encoding": "16UC1"}
    fields.update(kwargs)
    with pytest.raises(ImageCodecError):
        ImageSpec(**fields)


@pytest.mark.parametrize("kwargs", [
    {"version": True}, {"version": 0}, {"name": "../plugin"},
    {"options": {"x": float("nan")}}, {"options": {"x": []}}, {"options": []},
])
def test_invalid_codec_specs(kwargs):
    with pytest.raises(ImageCodecError):
        CodecSpec(**kwargs)


@pytest.mark.parametrize("bad_output", [np.zeros((6, 8), dtype=np.uint8), np.zeros((3, 4), dtype=np.uint16)])
def test_decoder_cannot_silently_change_shape_or_depth_type(bad_output):
    class BadDecoder:
        def decode(self, payload, image):
            return bad_output

    with pytest.raises(ImageCodecError, match="shape"):
        decode_pixels(BadDecoder(), b"payload", ImageSpec(8, 6, "16UC1", "depth"))


@pytest.mark.parametrize("bad_output", [b"", "text", np.zeros(4, dtype=np.uint8)])
def test_encoder_must_return_nonempty_bytes(bad_output):
    class BadEncoder:
        def encode(self, pixels, image):
            return bad_output

    spec = ImageSpec(8, 6, "rgb8")
    with pytest.raises(ImageCodecError, match="non-empty bytes"):
        encode_pixels(BadEncoder(), _pixels(spec), spec)
