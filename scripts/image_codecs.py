"""Image codec contracts, immutable descriptors, and explicit dependency injection.

A codec key identifies a bitstream, not a Python class. Encoders and decoders may
be implemented independently. File metadata never triggers imports or installs.
VRS transport and record compression are deliberately outside this module.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Protocol

import numpy as np

# ROS encoding -> VRS raw pixel format, canonical little-endian dtype, channels.
IMAGE_ENCODINGS = {
    "rgb8": ("RGB8", "u1", 3),
    "bgr8": ("BGR8", "u1", 3),
    "rgba8": ("RGBA8", "u1", 4),
    "mono8": ("GREY8", "u1", 1),
    "8UC1": ("GREY8", "u1", 1),
    "mono16": ("GREY16", "<u2", 1),
    "16UC1": ("GREY16", "<u2", 1),
    "32FC1": ("DEPTH32F", "<f4", 1),
}
MAX_IMAGE_BYTES = 256 * 1024 * 1024
MAX_ENCODED_BYTES = MAX_IMAGE_BYTES + 1024 * 1024


class ImageCodecError(ValueError):
    """Invalid, unsupported, or corrupt image codec input."""


@dataclass(frozen=True)
class ImageSpec:
    """Canonical unpadded pixels. Depth scale/units remain in sensor configuration."""

    width: int
    height: int
    encoding: str
    role: str = "image"

    def __post_init__(self) -> None:
        for key in ("width", "height"):
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, int) or not 0 < value < (1 << 32):
                raise ImageCodecError(f"Image {key} must be a positive uint32 integer")
        if not isinstance(self.encoding, str) or self.encoding not in IMAGE_ENCODINGS:
            raise ImageCodecError(f"Unsupported image encoding: {self.encoding!r}")
        if self.role not in ("image", "color", "depth"):
            raise ImageCodecError(f"Unsupported image role: {self.role!r}")
        if self.byte_count > MAX_IMAGE_BYTES:
            raise ImageCodecError("Decoded image exceeds the 256 MiB safety limit")

    @property
    def pixel_format(self) -> str:
        return IMAGE_ENCODINGS[self.encoding][0]

    @property
    def dtype(self) -> str:
        return IMAGE_ENCODINGS[self.encoding][1]

    @property
    def channels(self) -> int:
        return IMAGE_ENCODINGS[self.encoding][2]

    @property
    def shape(self) -> tuple[int, ...]:
        size = (self.height, self.width)
        return size if self.channels == 1 else (*size, self.channels)

    @property
    def byte_count(self) -> int:
        return self.width * self.height * self.channels * int(np.dtype(self.dtype).itemsize)

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> ImageSpec:
        if not isinstance(config, Mapping):
            raise ImageCodecError("Image configuration must be a mapping")
        try:
            role = config.get("image_role", "depth" if "depth_scale" in config else "image")
            return cls(config["width"], config["height"], config["encoding"], role)
        except KeyError as exc:
            raise ImageCodecError(f"Missing image property: {exc.args[0]}") from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "encoding": self.encoding,
            "image_role": self.role,
        }

    def array_from_bytes(self, data: bytes) -> Any:
        if not isinstance(data, bytes) or len(data) != self.byte_count:
            raise ImageCodecError(f"Image payload must contain exactly {self.byte_count} bytes")
        return np.frombuffer(data, dtype=np.dtype(self.dtype)).reshape(self.shape)

    def validate_array(self, image: Any) -> None:
        expected = np.dtype(self.dtype)
        if (
            not isinstance(image, np.ndarray)
            or image.shape != self.shape
            or image.dtype.kind != expected.kind
            or image.dtype.itemsize != expected.itemsize
        ):
            raise ImageCodecError(
                f"Decoded/encoded pixels must have shape {self.shape}, {expected}"
            )


@dataclass(frozen=True)
class CodecSpec:
    """Stable bitstream name/version and a snapshot of primitive JSON options."""

    name: str = "raw"
    version: int = 1
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not re.fullmatch(r"[a-z][a-z0-9_.-]{0,63}", self.name):
            raise ImageCodecError("Codec name must be a lowercase identifier")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version <= 0:
            raise ImageCodecError("Codec version must be a positive integer")
        if not isinstance(self.options, Mapping):
            raise ImageCodecError("Codec options must be a mapping")
        snapshot = dict(self.options)
        for key, value in snapshot.items():
            if not isinstance(key, str) or not isinstance(
                value, (str, int, float, bool, type(None))
            ):
                raise ImageCodecError("Codec options require string keys and primitive JSON values")
            if isinstance(value, float) and not math.isfinite(value):
                raise ImageCodecError("Codec options must be finite")
        object.__setattr__(self, "options", MappingProxyType(snapshot))

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "version": self.version, "options": dict(self.options)}


class ImageEncoder(Protocol):
    """Stateless per-frame encoder; must not mutate input pixels."""

    def validate(self, image: ImageSpec) -> None: ...

    def encode(self, pixels: Any, image: ImageSpec) -> bytes: ...


class ImageDecoder(Protocol):
    """Stateless per-frame decoder, returning original channel order and numeric type."""

    def validate(self, image: ImageSpec) -> None: ...

    def decode(self, payload: bytes, image: ImageSpec) -> Any: ...


EncoderFactory = Callable[[CodecSpec], ImageEncoder]
DecoderFactory = Callable[[CodecSpec], ImageDecoder]


class CodecRegistry:
    """Instance-owned registry; no dynamic imports and no silent fallback."""

    def __init__(self) -> None:
        self._encoders: dict[tuple[str, int], tuple[EncoderFactory, bool]] = {}
        self._decoders: dict[tuple[str, int], DecoderFactory] = {}

    def copy(self) -> CodecRegistry:
        result = CodecRegistry()
        result._encoders = self._encoders.copy()
        result._decoders = self._decoders.copy()
        return result

    def register_encoder(
        self, name: str, version: int, factory: EncoderFactory, *, lossless: bool
    ) -> None:
        key = self._key(name, version)
        if key in self._encoders:
            raise ImageCodecError(f"Encoder already registered: {key}")
        if not callable(factory) or not isinstance(lossless, bool):
            raise ImageCodecError("Encoder registration requires a factory and boolean lossless")
        self._encoders[key] = (factory, lossless)

    def register_decoder(self, name: str, version: int, factory: DecoderFactory) -> None:
        key = self._key(name, version)
        if key in self._decoders:
            raise ImageCodecError(f"Decoder already registered: {key}")
        if not callable(factory):
            raise ImageCodecError("Decoder registration requires a factory")
        self._decoders[key] = factory

    @staticmethod
    def _key(name: str, version: int) -> tuple[str, int]:
        spec = CodecSpec(name, version)
        return spec.name, spec.version

    def encoder(self, codec: CodecSpec, image: ImageSpec) -> tuple[ImageEncoder, bool]:
        try:
            factory, lossless = self._encoders[(codec.name, codec.version)]
        except KeyError as exc:
            raise ImageCodecError(
                f"Unsupported image encoder: {codec.name}@{codec.version}"
            ) from exc
        # Lossy depth needs a future explicit quantization/error-budget contract.
        if image.role == "depth" and not lossless:
            raise ImageCodecError("Lossy depth codecs are not enabled")
        encoder = factory(codec)
        encoder.validate(image)
        return encoder, lossless

    def decoder(self, codec: CodecSpec, image: ImageSpec) -> ImageDecoder:
        try:
            factory = self._decoders[(codec.name, codec.version)]
        except KeyError as exc:
            raise ImageCodecError(
                f"Unsupported image decoder: {codec.name}@{codec.version}"
            ) from exc
        decoder = factory(codec)
        decoder.validate(image)
        return decoder


def default_codec_registry() -> CodecRegistry:
    """Return a fresh built-in registry. Applications may extend their own copy."""
    from scripts.image_codec_builtin import OpenCVImageCodec, RawImageCodec

    result = CodecRegistry()
    for name, factory, lossless in (
        ("raw", RawImageCodec, True),
        ("png", OpenCVImageCodec, True),
        ("jpeg", OpenCVImageCodec, False),
    ):
        result.register_encoder(name, 1, factory, lossless=lossless)
        result.register_decoder(name, 1, factory)
    return result


@dataclass(frozen=True)
class ImageCodecDescriptor:
    """Self-contained per-stream restoration contract, independent of its carrier."""

    image: ImageSpec
    codec: CodecSpec
    lossless: bool

    def __post_init__(self) -> None:
        if not isinstance(self.image, ImageSpec) or not isinstance(self.codec, CodecSpec):
            raise ImageCodecError("Descriptor requires ImageSpec and CodecSpec")
        if not isinstance(self.lossless, bool):
            raise ImageCodecError("lossless must be a boolean")
        if self.image.role == "depth" and not self.lossless:
            raise ImageCodecError("Lossy depth codecs are not enabled")

    def to_json(self) -> str:
        return json.dumps(
            {
                "descriptor_version": 1,
                "image": self.image.to_dict(),
                "codec": self.codec.to_dict(),
                "lossless": self.lossless,
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @classmethod
    def from_json(cls, value: str) -> ImageCodecDescriptor:
        try:
            data = json.loads(value)
            if type(data["descriptor_version"]) is not int or data["descriptor_version"] != 1:
                raise ImageCodecError("Unsupported image codec descriptor version")
            codec = data["codec"]
            return cls(
                ImageSpec.from_config(data["image"]),
                CodecSpec(codec["name"], codec["version"], codec["options"]),
                data["lossless"],
            )
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ImageCodecError("Invalid image codec descriptor") from exc


def encode_pixels(encoder: ImageEncoder, pixels: Any, image: ImageSpec) -> bytes:
    """Validate the strategy's input and output; return one independently decodable frame."""
    image.validate_array(pixels)
    payload = encoder.encode(pixels, image)
    if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_ENCODED_BYTES:
        raise ImageCodecError("Encoder must return non-empty bytes within the size limit")
    return payload


def decode_pixels(decoder: ImageDecoder, payload: bytes, image: ImageSpec) -> Any:
    """Validate restoration before canonicalizing byte order (never quantize or narrow)."""
    if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_ENCODED_BYTES:
        raise ImageCodecError("Invalid encoded image size or type")
    pixels = decoder.decode(payload, image)
    image.validate_array(pixels)
    return np.ascontiguousarray(pixels, dtype=np.dtype(image.dtype))
