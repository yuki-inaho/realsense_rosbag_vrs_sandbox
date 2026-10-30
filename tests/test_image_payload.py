"""Reject malformed ROS images before they can become mislabeled VRS records."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from scripts.image_payload import image_payload


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"step": 5}, "step"),
        ({"data": bytes(11)}, "payload"),
        ({"data": bytes(13)}, "payload"),
        ({"width": 3}, "width changed"),
        ({"encoding": "bgr8"}, "encoding changed"),
        ({"encoding": "unknown"}, "Unsupported"),
        ({"height": 0}, "positive"),
    ],
)
def test_invalid_image_layout_is_rejected(changes: dict[str, Any], error: str) -> None:
    fields = {
        "width": 2,
        "height": 2,
        "encoding": "rgb8",
        "step": 6,
        "is_bigendian": 0,
        "data": bytes(range(12)),
    }
    fields.update(changes)
    with pytest.raises(ValueError, match=error):
        image_payload(SimpleNamespace(**fields), {"width": 2, "height": 2, "encoding": "rgb8"})
