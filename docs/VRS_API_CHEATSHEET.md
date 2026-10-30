# VRS API チートシート

**更新日: 2026-10-30 / パッケージ版: 0.1.0 / 保存形式版: 2**

現行実装は [scripts/vrs_writer.py](../scripts/vrs_writer.py) から、公式パッケージ `vrs==1.2.2` の `vrsbindings.Writer` を呼びます。自作 C++ 拡張、`pyvrs` の公開名の追加、圧縮列挙名の書き換えは使用しません。

## 書き込みと読み戻しの完全例

以下は、人工の RGB・深度・加速度を一時ファイルへ保存し、リポジトリのリーダーで読み戻す例です。画像バイト数は設定した寸法・画素型と一致させます。

```python
import struct
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from scripts.vrs_reader import VRSReader
from scripts.vrs_writer import VRSWriter

rgb = np.arange(12, dtype=np.uint8).reshape(2, 2, 3)
depth = np.array([[0, 100], [1000, 65535]], dtype="<u2")
acceleration = (0.25, -0.5, 9.75)

with TemporaryDirectory(prefix="vrs-example-") as directory:
    output = Path(directory) / "example.vrs"
    with VRSWriter(output, compression="lz4") as writer:
        writer.add_stream(1001, "Example_Color")
        writer.add_stream(1002, "Example_Depth")
        writer.add_stream(1003, "Example_Accel")
        writer.add_stream(2001, "Example_Device")

        writer.write_configuration(1001, {"width": 2, "height": 2, "encoding": "rgb8"})
        writer.write_configuration(
            1002,
            {"width": 2, "height": 2, "encoding": "16UC1", "depth_scale": 0.002},
        )
        writer.write_configuration(
            1003,
            {"sensor_type": "accelerometer", "unit": "m/s^2", "axes": ["x", "y", "z"]},
        )
        writer.write_configuration(2001, {"info_type": "device", "device_name": "Synthetic"})

        # 全ストリームと設定を登録してからデータを書き始めます。
        writer.write_data(1001, 0.125, rgb.tobytes())
        writer.write_data(1002, 0.125, depth.tobytes())
        writer.write_data(1003, 0.126, struct.pack("<ddd", *acceleration))

    with VRSReader(output) as reader:
        assert reader.get_stream_ids() == [1001, 1002, 1003, 2001]
        rgb_record = next(reader.read_data_records(1001))
        depth_record = next(reader.read_data_records(1002))
        imu_record = next(reader.read_data_records(1003))

        np.testing.assert_array_equal(
            np.frombuffer(rgb_record["data"], dtype=np.uint8).reshape(2, 2, 3), rgb
        )
        np.testing.assert_array_equal(
            np.frombuffer(depth_record["data"], dtype="<u2").reshape(2, 2), depth
        )
        assert struct.unpack("<ddd", imu_record["data"]) == acceleration
        assert reader.read_configuration(1002)["depth_scale"] == 0.002
        assert reader.get_record_count(2001) == 0
```

設定のみのストリームにも Configuration レコードが作成されます。空の Data レコードを追加する必要はありません。

## 公式 PyVRS リーダーから直接読む

既存の `output.vrs` を読み出す例です。`SyncVRSReader` は生成時にファイルを開き、直接反復処理できます。`open()` や `records()` の追加呼び出しは不要です。

```python
import json

import pyvrs

reader = pyvrs.SyncVRSReader("output.vrs")
reader.set_image_conversion(pyvrs.ImageConversion.OFF)
try:
    for stream_id, tags in reader.stream_tags.items():
        logical_id = int(tags["user_stream_id"])
        configuration = json.loads(tags["config_json"])
        print(stream_id, logical_id, tags["payload_encoding"], configuration)

    for record in reader:
        if record.record_type != "data":
            continue
        tags = reader.stream_tags[record.stream_id]
        if tags["payload_encoding"] == "native_image":
            image = record.image_blocks[0]
            print(record.timestamp, image.shape, image.dtype)
        elif tags["payload_encoding"] == "imu_xyz_f64le":
            xyz = record.metadata_blocks[0]["doubles"]
            print(record.timestamp, xyz)
finally:
    reader.close()
```

`ImageConversion.OFF` は深度の表示向け変換を無効にするために指定します。640×480 の RGB は `(480, 640, 3)`・`uint8`、16UC1 深度は `(480, 640)`・`uint16` として読み出せます。

## 保存規約

定義の参照元は [scripts/vrs_schema.py](../scripts/vrs_schema.py) です。

| タグ | 意味 |
|---|---|
| `vrs_sandbox_schema_version` | 現行は文字列 `"2"` |
| `user_stream_id` | 論理ストリーム番号。VRS が採番する実ストリーム ID とは区別します |
| `user_stream_name` | 論理ストリーム名 |
| `config_json` | センサー設定を JSON 化した文字列 |
| `payload_encoding` | 次表の格納方法 |

| `payload_encoding` | 公式 VRS での格納先 | リポジトリの `read_data_records()` の戻り値 |
|---|---|---|
| `native_image` | 本来の寸法・画素型を持つ画像ブロック | 行余白を除いた画像バイト列 |
| `imu_xyz_f64le` | 数値メタデータ `doubles` の3成分 | リトルエンディアン double 3個、24バイト |
| `opaque_base64` | 文字列メタデータ `some_string` に Base64 | 復号した元のバイト列 |

未知のバイト列は画像に見せかけず、`opaque_base64` と明示します。設定のみのストリームは Data レコードを持ちません。

## 書き込み時の契約

- `add_stream()` と `write_configuration()` は、最初の `write_data()` より前にすべて呼び出します。書き込み開始後の登録・設定変更はエラーです。
- 時刻の単位は秒です。全ストリームを通じて非減少とし、同じ時刻の複数レコードは許可します。NaN・無限大・負の時刻は拒否します。
- 画像は設定と一致するバイト数、IMU は double 3個分の24バイトが必要です。
- 対応画像符号化は `rgb8`・`bgr8`・`rgba8`・`mono8`・`8UC1`・`mono16`・`16UC1`・`32FC1` です。
- `close()` は最後の時刻のレコードまで書き出し、複数回呼んでも安全です。例外発生時にはネイティブライターの終了処理を行います。

既定では、待機中のペイロードが **16 MiB**、または Data レコードが **256件**に達すると書き出します。`VRSWriter(path, flush_bytes=..., flush_records=...)` で調整できます。別途、公式ライターの背景書き込みキューが 64 MiB を超える場合は排出を待ち、30秒以内に閾値以下にならなければエラーにします。これらはプロセス全体のメモリ量の上限ではありません。単一の大きなレコードは閾値を超えることがあります。

## 変換 API

既存の入力 bag を変換する例です。

```python
from pathlib import Path

from scripts.rosbag_to_vrs_converter import RosbagToVRSConverter, create_rgbd_imu_config

converter = RosbagToVRSConverter(
    Path("input.bag"),
    Path("output.vrs"),
    create_rgbd_imu_config(compression="zstd"),
)
result = converter.convert()
print(result.messages_per_stream)
print(result.duration_sec)
```

`create_rgbd_config()` は画像と Transform、`create_rgbd_imu_config()` は IMU と周辺情報を含みます。`total_messages` と `messages_per_stream` は出力した Data レコード数で、設定だけの入力メッセージは数えません。

## 互換性と検証

保存形式バージョンがない旧ファイルについて、リーダーは1行 GREY8 に入れたバイト列と旧 CUSTOM ブロックを読む処理を保持しています。旧 GREY8 形式の再生成による回帰は [tests/test_vrs_reader_compatibility.py](../tests/test_vrs_reader_compatibility.py) にあります。任意の過去ファイルすべてを検証したものではありません。

公式の `sample`／`sample_with_image` 作成処理を使用するため、記録型はサンプル用の `UnitTest1` です。画像の寸法・画素型が正しくても、Aria などの機器固有の記録型への対応は保証しません。

```bash
uv run pytest -q -m "not integration"
uv run pytest -q -m e2e
REALSENSE_ROSBAG_PATH=/absolute/path/to/sample.bag uv run pytest -q -m integration
```

詳細なテスト条件は [SYNTHETIC_E2E.md](SYNTHETIC_E2E.md)、公式 API の実装は [PyVRS 1.2.2 の書き込み実装](https://github.com/facebookresearch/pyvrs/tree/v1.2.2/csrc/writer)を参照してください。
