"""Built-in codec strategies. OpenCV is an implementation detail, not a file identifier."""

from __future__ import annotations

import struct
from typing import Any

import numpy as np

from scripts.image_codecs import CodecSpec, ImageCodecError, ImageSpec


def _integer_option(codec: CodecSpec, key: str, default: int, low: int, high: int) -> int:
    unknown = codec.options.keys() - {key}
    if unknown:
        raise ImageCodecError(f"Unknown {codec.name} options: {sorted(unknown)}")
    value = codec.options.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ImageCodecError(f"{codec.name} {key} must be an integer in [{low}, {high}]")
    return value


class RawImageCodec:
    def __init__(self, codec: CodecSpec) -> None:
        if codec.name != "raw" or codec.version != 1 or codec.options:
            raise ImageCodecError("raw@1 accepts no options")

    def validate(self, image: ImageSpec) -> None:
        pass

    def encode(self, pixels: Any, image: ImageSpec) -> bytes:
        return bytes(np.ascontiguousarray(pixels, dtype=np.dtype(image.dtype)).tobytes())

    def decode(self, payload: bytes, image: ImageSpec) -> Any:
        return image.array_from_bytes(payload)


def _encoded_dimensions(payload: bytes, codec: str) -> tuple[int, int]:
    """Read dimensions before allocating decoded pixels; reject format substitution."""
    if codec == "png":
        if len(payload) < 33 or payload[:8] != b"\x89PNG\r\n\x1a\n" or payload[12:16] != b"IHDR":
            raise ImageCodecError("Invalid PNG header")
        return struct.unpack(">II", payload[16:24])
    if not payload.startswith(b"\xff\xd8") or not payload.endswith(b"\xff\xd9"):
        raise ImageCodecError("Invalid JPEG header or end marker")
    offset = 2
    while offset < len(payload):
        if payload[offset] != 0xFF:
            break
        while offset < len(payload) and payload[offset] == 0xFF:
            offset += 1
        if offset >= len(payload):
            break
        marker = payload[offset]
        offset += 1
        if marker in (0x01, 0xD8) or 0xD0 <= marker <= 0xD7:
            continue
        if marker in (0xDA, 0xD9) or offset + 2 > len(payload):
            break
        length = int.from_bytes(payload[offset : offset + 2], "big")
        if length < 2 or offset + length > len(payload):
            break
        if marker in (0xC0, 0xC1, 0xC2) and length >= 8:
            height, width = struct.unpack(">HH", payload[offset + 3 : offset + 7])
            return width, height
        offset += length
    raise ImageCodecError("JPEG has no supported frame header")


class OpenCVImageCodec:
    """PNG preserves uint8/uint16 values; JPEG is intentionally limited to 8-bit color/mono."""

    def __init__(self, codec: CodecSpec) -> None:
        if codec.version != 1 or codec.name not in ("png", "jpeg"):
            raise ImageCodecError("Unsupported OpenCV codec")
        self.name = codec.name
        self.option = (
            _integer_option(codec, "compression_level", 3, 0, 9)
            if self.name == "png"
            else _integer_option(codec, "quality", 95, 1, 100)
        )

    def validate(self, image: ImageSpec) -> None:
        if self.name == "jpeg":
            if image.role == "depth" or image.encoding not in ("rgb8", "bgr8", "mono8", "8UC1"):
                raise ImageCodecError("JPEG accepts only 8-bit color/mono, never depth or alpha")
        elif image.encoding == "32FC1":
            raise ImageCodecError("PNG cannot preserve float32 depth; use raw or a lossless plugin")

    @staticmethod
    def _swap_channels(pixels: Any, image: ImageSpec) -> Any:
        if image.encoding == "rgb8":
            return np.ascontiguousarray(pixels[..., ::-1])
        if image.encoding == "rgba8":
            return np.ascontiguousarray(pixels[..., [2, 1, 0, 3]])
        return np.ascontiguousarray(pixels)

    def encode(self, pixels: Any, image: ImageSpec) -> bytes:
        import cv2

        self.validate(image)
        image.validate_array(pixels)
        # OpenCV expects BGR/BGRA and host-endian numeric pixels.
        pixels = self._swap_channels(pixels, image).astype(np.dtype(image.dtype).newbyteorder("="))
        flag = cv2.IMWRITE_PNG_COMPRESSION if self.name == "png" else cv2.IMWRITE_JPEG_QUALITY
        suffix = ".png" if self.name == "png" else ".jpg"
        try:
            ok, encoded = cv2.imencode(suffix, pixels, [flag, self.option])
        except cv2.error as exc:
            raise ImageCodecError(f"{self.name} encoding failed: {exc}") from exc
        if not ok:
            raise ImageCodecError(f"{self.name} encoding failed")
        return bytes(encoded.tobytes())

    def decode(self, payload: bytes, image: ImageSpec) -> Any:
        import cv2

        self.validate(image)
        if _encoded_dimensions(payload, self.name) != (image.width, image.height):
            raise ImageCodecError("Encoded dimensions disagree with the image descriptor")
        try:
            pixels = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        except cv2.error as exc:
            raise ImageCodecError(f"{self.name} decoding failed: {exc}") from exc
        if pixels is None:
            raise ImageCodecError(f"Corrupt {self.name} payload")
        image.validate_array(pixels)
        return self._swap_channels(pixels, image)
