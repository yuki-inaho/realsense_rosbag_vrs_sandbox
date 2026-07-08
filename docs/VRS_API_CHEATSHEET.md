# VRS API チートシート

このリポジトリで使う VRS / PyVRS API の最小リファレンスです。

---

## 読み込み

### Repository reader

通常は `scripts.vrs_reader.VRSReader` を使います。logical stream id、configuration JSON、payload bytes をリポジトリの writer adapter と同じ規約で復元します。

```python
from scripts.vrs_reader import VRSReader

with VRSReader("output.vrs") as reader:
    print(reader.get_stream_ids())
    config = reader.read_configuration(1001)
    records = list(reader.read_data_records(1001))

print(config["encoding"])
print(records[0]["timestamp"], records[0]["data"])
```

### Raw PyVRS reader

公式 reader を直接使う場合は `SyncVRSReader` を iterable として扱います。

```python
import pyvrs

reader = pyvrs.SyncVRSReader("output.vrs")

for stream_id in reader.stream_ids:
    print(stream_id, reader.get_stream_info(stream_id))

for record in reader:
    print(record.stream_id, record.record_type, record.timestamp)
    if record.n_metadata_blocks:
        print(record.metadata_blocks[0])
    if getattr(record, "n_image_blocks", 0):
        payload = record.image_blocks[0].tobytes()
```

`reader.stream_tags` には repository adapter が保存する `user_stream_id`, `user_stream_name`, `config_json` が入ります。

---

## 書き込み

### Repository writer adapter

通常は `scripts.vrs_writer.VRSWriter` を使います。公式 PyVRS writer の上に、既存 converter-facing API を維持する薄い adapter を置いています。

```python
from scripts.vrs_writer import VRSWriter

with VRSWriter("output.vrs", compression="lz4") as writer:
    writer.add_stream(1001, "RealSense_D435i_Color")
    writer.write_configuration(
        1001,
        {"width": 640, "height": 480, "encoding": "rgb8"},
    )
    writer.write_data(1001, 0.125, b"image-bytes")
```

対応 compression は `lz4`, `zstd`, `none` です。

### 公式 PyVRS writer loader

PyPI `vrs==1.2.2` の `pyvrs.writer` は direct import 時に native symbol export 欠落で失敗するため、site-packages は変更せず loader 内で補正します。

```python
from scripts.vrs_writer import load_official_writer_backend

import_path, writer_cls, pyvrs = load_official_writer_backend()
assert import_path == "pyvrs.writer.VRSWriter"
```

adapter は公式 writer の `sample_with_image` factory を使います。logical stream id と configuration は stream tags、payload は image block に保存します。これにより repository reader との roundtrip は可能ですが、外部 VRS consumer 向けの意味論的 recordable 型は未保証です。

---

## 変換

```python
from pathlib import Path

from scripts.rosbag_to_vrs_converter import (
    RosbagToVRSConverter,
    create_rgbd_config,
    create_rgbd_imu_config,
)

converter = RosbagToVRSConverter(
    Path("input.bag"),
    Path("output.vrs"),
    create_rgbd_imu_config(compression="lz4"),
)
result = converter.convert()
print(result.messages_per_stream)
```

テストでは `reader_factory` と `writer_factory` を明示注入できます。通常経路で暗黙の fallback はしません。

---

## 回帰テスト

```bash
uv run pytest -q -m "not integration"
uv run pytest -q tests/test_official_pyvrs_writer.py tests/test_vrs_writer_adapter.py
uv run pytest -q tests/test_converter_synthetic.py tests/test_cli_smoke.py
REALSENSE_ROSBAG_PATH=/absolute/path/to/sample.bag uv run pytest -q -m integration
```

実 rosbag がない環境では integration tests は skip または deselect されます。
