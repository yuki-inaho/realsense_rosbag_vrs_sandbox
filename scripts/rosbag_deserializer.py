"""Helpers for deserializing ROSbag messages.

RealSense Viewer ROS1 bags can contain valid messages with a small trailing
payload. ``rosbags`` intentionally asserts full-byte consumption in its public
``deserialize`` path, so use this helper where the project needs to tolerate
that known ROS1 recording shape.
"""

from __future__ import annotations

from typing import Any


def deserialize_ros1_lenient(typestore: Any, rawdata: bytes, msgtype: str) -> Any:
    """Deserialize a ROS1 message and tolerate unused trailing bytes."""
    msgdef = typestore.get_msgdef(msgtype)
    message, pos = msgdef.deserialize_ros1(rawdata, 0, msgdef.cls, typestore)
    if pos > len(rawdata):
        raise ValueError(f"Deserializer overran message: pos={pos}, len={len(rawdata)}")
    return message


def deserialize_reader_message(reader: Any, rawdata: bytes, msgtype: str) -> Any:
    """Deserialize through ``AnyReader`` with a ROS1 lenient fallback."""
    try:
        return reader.deserialize(rawdata, msgtype)
    except AssertionError:
        if getattr(reader, "is2", False):
            raise
        typestore = getattr(reader, "typestore", None)
        if typestore is None:
            raise
        return deserialize_ros1_lenient(typestore, rawdata, msgtype)
