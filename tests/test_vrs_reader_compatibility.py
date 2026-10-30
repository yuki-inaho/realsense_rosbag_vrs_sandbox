"""Keep files produced by the pre-v2 official writer adapter readable."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import vrsbindings

from scripts.vrs_reader import VRSReader


def test_legacy_one_row_image_payload_and_tags_remain_readable(tmp_path: Path) -> None:
    """Generate the old on-disk format through official bindings, without a v2 tag."""
    path = tmp_path / "legacy.vrs"
    writer = vrsbindings.Writer()
    stream = writer.createStream("sample_with_image")
    configuration = {"width": 2, "height": 1, "encoding": "rgb8", "camera_k": [1.0] * 9}
    stream.setTag("user_stream_id", "1001")
    stream.setTag("user_stream_name", "Legacy camera")
    stream.setTag("config_json", json.dumps(configuration))
    config_format = stream.createRecordFormat(vrsbindings.RecordType.CONFIGURATION)
    metadata = config_format.getMembers()[0]
    metadata["image_width"].set(6)
    metadata["image_height"].set(1)
    metadata["image_pixel_format"].set(vrsbindings.PixelFormat.GREY8.value)
    stream.createRecord(0.0, config_format)
    data_format = stream.createRecordFormat(vrsbindings.RecordType.DATA)
    metadata = data_format.getMembers()[0]
    metadata["camera_id"].set(1001)
    metadata["room_temperature"].set(0.0)
    metadata["doubles"].set([0.0] * 3)
    metadata["some_string"].set("")
    metadata["some_string_int_map"].set({"payload_len": 5})
    payload = b"\x00\xffRGB"
    stream.createRecord(0.125, data_format, np.frombuffer(payload + b"\x00", dtype=np.uint8))
    try:
        assert writer.create(str(path)) == 0
        assert writer.writeRecords(1.0) == 0
    finally:
        assert writer.close() == 0

    with VRSReader(path) as reader:
        assert reader.get_stream_ids() == [1001]
        assert reader.read_configuration(1001) == configuration
        assert list(reader.read_data_records(1001)) == [{"timestamp": 0.125, "data": payload}]
