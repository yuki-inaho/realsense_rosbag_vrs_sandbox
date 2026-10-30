"""Validate ROS image layouts and produce packed little-endian VRS pixels."""

from __future__ import annotations

from typing import Any, cast

import numpy as np

# ROS aliases map to one explicit encoding understood by the official writer.
_FORMATS = {
    "rgb8": ("rgb8", "u1", 3),
    "bgr8": ("bgr8", "u1", 3),
    "rgba8": ("rgba8", "u1", 4),
    "mono8": ("mono8", "u1", 1),
    "8uc1": ("mono8", "u1", 1),
    "16uc1": ("16UC1", "u2", 1),
    "mono16": ("16UC1", "u2", 1),
    "z16": ("16UC1", "u2", 1),
    "32fc1": ("32FC1", "f4", 1),
}


def _layout(message: Any) -> tuple[int, int, str, str, int]:
    width, height = int(message.width), int(message.height)
    if width <= 0 or height <= 0:
        raise ValueError("Image width and height must be positive")
    encoding = str(message.encoding).lower()
    if encoding not in _FORMATS:
        raise ValueError(f"Unsupported ROS image encoding: {message.encoding}")
    canonical, dtype, channels = _FORMATS[encoding]
    return width, height, canonical, dtype, channels


def image_description(message: Any) -> dict[str, Any]:
    """Describe the actual image message instead of guessing from the stream name."""
    width, height, encoding, _, _ = _layout(message)
    return {"width": width, "height": height, "encoding": encoding}


def image_payload(message: Any, configuration: dict[str, Any]) -> bytes:
    """Remove row padding and normalize byte order without changing pixel values.

    A change of dimensions or encoding requires a new stream/configuration;
    silently reshaping such messages would corrupt the interpretation of data.
    """
    width, height, encoding, dtype_code, channels = _layout(message)
    for field, value in (("width", width), ("height", height), ("encoding", encoding)):
        if configuration[field] != value:
            raise ValueError(f"Image {field} changed: {configuration[field]!r} -> {value!r}")
    dtype = np.dtype(dtype_code)
    row_bytes = width * channels * dtype.itemsize
    step = int(message.step)
    if step < row_bytes:
        raise ValueError(f"Image step {step} is smaller than its {row_bytes}-byte pixel row")
    data = bytes(message.data)
    expected_size = height * step
    if len(data) != expected_size:
        raise ValueError(f"Image payload has {len(data)} bytes; expected {expected_size}")
    rows = np.frombuffer(data, dtype=np.uint8).reshape(height, step)
    packed = rows[:, :row_bytes].tobytes()
    if dtype.itemsize > 1:
        byte_order = ">" if bool(message.is_bigendian) else "<"
        values = np.frombuffer(packed, dtype=dtype.newbyteorder(byte_order))
        packed = values.astype(dtype.newbyteorder("<"), copy=False).tobytes()
    return cast(bytes, packed)
