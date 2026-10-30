"""Versioned encoded-image carrier for the official PyVRS 1.2.2 sample factory.

The factory exposes metadata strings but no configurable JPG/PNG content block.
Store explicit base64 metadata, not a fictitious RAW image. This adapter can be
replaced with native compressed blocks without changing codec strategies.
"""

from __future__ import annotations

import base64
import binascii
from typing import Any

from scripts.image_codecs import (
    MAX_ENCODED_BYTES,
    CodecRegistry,
    ImageCodecDescriptor,
    ImageCodecError,
    decode_pixels,
)

CODEC_SCHEMA_VERSION = "3"
CODEC_IMAGE = "image_codec_base64_v1"
IMAGE_CODEC_TAG = "image_codec_json"


def encode_payload_text(payload: bytes) -> str:
    if not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_ENCODED_BYTES:
        raise ImageCodecError("Invalid encoded image size or type")
    return base64.b64encode(payload).decode("ascii")


def decode_payload_text(text: Any) -> bytes:
    if not isinstance(text, str) or not 0 < len(text) <= 4 * ((MAX_ENCODED_BYTES + 2) // 3):
        raise ImageCodecError("Invalid base64 image payload size or type")
    try:
        data = base64.b64decode(text, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ImageCodecError("Invalid base64 image payload") from exc
    if not data or len(data) > MAX_ENCODED_BYTES:
        raise ImageCodecError("Invalid encoded image size")
    return data


class ImageRecordDecoder:
    """Resolve once per stream; subsequent frames use the same restoration strategy."""

    def __init__(self, descriptor_json: str, registry: CodecRegistry) -> None:
        self.descriptor = ImageCodecDescriptor.from_json(descriptor_json)
        self._decoder = registry.decoder(self.descriptor.codec, self.descriptor.image)

    def decode(self, text: Any) -> bytes:
        pixels = decode_pixels(self._decoder, decode_payload_text(text), self.descriptor.image)
        return bytes(pixels.tobytes())
