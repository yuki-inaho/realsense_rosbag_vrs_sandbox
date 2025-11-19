# VRS API チートシート

VRS (Virtual Reality Stream) APIの逆引きリファレンス

---

## 目次

1. [PyVRS (読み込み)](#pyvrs-読み込み)
2. [pyvrs_writer (書き込み)](#pyvrs_writer-書き込み)
3. [データ構造](#データ構造)
4. [よくあるタスク](#よくあるタスク)

---

## PyVRS (読み込み)

### VRSファイルを開く

```python
import pyvrs

# VRSファイルを開く
reader = pyvrs.SyncVRSReader("file.vrs")
reader.open()

# 使用後は必ず閉じる
reader.close()
```

### ストリーム一覧を取得

```python
# すべてのストリームを取得
streams = reader.get_streams()

for stream in streams:
    print(f"Stream ID: {stream.stream_id}")
    print(f"  Recordable Type: {stream.recordable_type_id}")
    print(f"  Flavor: {stream.flavor}")
```

### レコードを読み取る

```python
# すべてのレコードをイテレート
for record in reader.records():
    print(f"Stream ID: {record.stream_id.numeric_name}")
    print(f"Timestamp: {record.timestamp}")
    print(f"Record Type: {record.record_type}")  # CONFIGURATION, STATE, DATA
```

### Configuration レコードを読み取る

```python
# Configuration レコードのみフィルタ
config_records = [r for r in reader.records()
                 if r.record_type == pyvrs.RecordType.CONFIGURATION]

for record in config_records:
    # メタデータブロック（JSONデータ）を取得
    if record.metadata_blocks:
        metadata = record.metadata_blocks[0]
        print(f"Configuration: {metadata}")
```

### Data レコードを読み取る

```python
# Data レコードのみフィルタ
data_records = [r for r in reader.records()
               if r.record_type == pyvrs.RecordType.DATA]

for record in data_records:
    timestamp = record.timestamp

    # カスタムブロック（画像データ等）を取得
    if record.custom_blocks:
        data = record.custom_blocks[0]
        print(f"Data size: {len(data)} bytes")
```

---

## pyvrs_writer (書き込み)

### VRSファイルを作成

```python
from pyvrs_writer import VRSWriter

# VRSファイルを作成（コンテキストマネージャ推奨）
with VRSWriter("output.vrs") as writer:
    # ストリーム追加
    writer.add_stream(1001, "CameraStream_Color")

    # Configuration書き込み
    writer.write_configuration(1001, {"width": 640, "height": 480})

    # Data書き込み
    writer.write_data(1001, 1234567890.123, b'image_data_here')
```

### ストリームを追加

```python
writer = VRSWriter("output.vrs")

# ストリーム追加（ID, flavor名）
writer.add_stream(1001, "RealSense_Color")
writer.add_stream(1002, "RealSense_Depth")

# 重複チェックは自動で行われる
```

### Configuration レコードを書き込む

```python
# Configurationは辞書形式
config_data = {
    "width": 640,
    "height": 480,
    "encoding": "rgb8",
    "camera_k": [fx, 0, cx, 0, fy, cy, 0, 0, 1],
    "camera_d": [k1, k2, p1, p2, k3],
    "distortion_model": "plumb_bob"
}

writer.write_configuration(stream_id=1001, config=config_data)
```

### Data レコードを書き込む

```python
# タイムスタンプとバイナリデータを指定
timestamp = 1234567890.123  # Unix timestamp (float)
image_bytes = b'\x00\x01\x02...'  # バイナリデータ

writer.write_data(
    stream_id=1001,
    timestamp=timestamp,
    data=image_bytes
)
```

### ファイルを閉じる

```python
# 明示的に閉じる
writer.close()

# またはコンテキストマネージャで自動クローズ
with VRSWriter("output.vrs") as writer:
    # ... 書き込み処理
    pass  # ブロック終了時に自動でclose()が呼ばれる
```

---

## データ構造

### StreamId

```python
# ストリームIDは数値で指定
stream_id = 1001

# VRSでは内部的にRecordableTypeIDとInstanceIDの組み合わせ
# 例: RecordableTypeID=1, InstanceID=1 → 1001
```

### RecordType

```python
import pyvrs

# 3種類のレコードタイプ
pyvrs.RecordType.CONFIGURATION  # 設定情報（最初に1回）
pyvrs.RecordType.STATE         # 状態変化（オプション）
pyvrs.RecordType.DATA          # データ（多数）
```

### Timestamp

```python
# Unix timestamp (秒単位、float)
import time

timestamp = time.time()  # 1234567890.123456
```

---

## よくあるタスク

### タスク1: VRSファイルの内容を表示

```python
import pyvrs

reader = pyvrs.SyncVRSReader("file.vrs")
reader.open()

# ストリーム一覧
streams = reader.get_streams()
print(f"Total streams: {len(streams)}")

# 各ストリームの情報
for stream in streams:
    print(f"\nStream {stream.stream_id}:")

    # レコード数をカウント
    config_count = sum(1 for r in reader.records()
                      if r.stream_id == stream.stream_id
                      and r.record_type == pyvrs.RecordType.CONFIGURATION)
    data_count = sum(1 for r in reader.records()
                    if r.stream_id == stream.stream_id
                    and r.record_type == pyvrs.RecordType.DATA)

    print(f"  Configuration records: {config_count}")
    print(f"  Data records: {data_count}")

reader.close()
```

### タスク2: ROSbag Image を VRS に変換

```python
from pyvrs_writer import VRSWriter
import struct

# sensor_msgs/Image から変換
def convert_image_to_vrs(writer, stream_id, msg, timestamp):
    """
    ROSメッセージ (sensor_msgs/Image) をVRSに書き込む

    Args:
        writer: VRSWriter instance
        stream_id: int
        msg: sensor_msgs/Image
        timestamp: float (Unix timestamp)
    """
    # 画像データを取得（すでにバイト列）
    image_data = bytes(msg.data) if not isinstance(msg.data, bytes) else msg.data

    # VRSに書き込み
    writer.write_data(stream_id, timestamp, image_data)
```

### タスク3: カメラ内部パラメータを保存

```python
from pyvrs_writer import VRSWriter

# sensor_msgs/CameraInfo から Configuration を作成
def write_camera_config(writer, stream_id, camera_info):
    """
    カメラ内部パラメータをConfigurationレコードとして保存

    Args:
        writer: VRSWriter instance
        stream_id: int
        camera_info: sensor_msgs/CameraInfo
    """
    config = {
        "width": int(camera_info.width),
        "height": int(camera_info.height),
        "camera_k": list(camera_info.K),  # 3x3行列（row-major, 9要素）
        "camera_d": list(camera_info.D),  # 歪み係数（5要素）
        "distortion_model": camera_info.distortion_model,
        "frame_id": camera_info.header.frame_id
    }

    writer.write_configuration(stream_id, config)
```

### タスク4: IMUデータを保存

```python
from pyvrs_writer import VRSWriter
import struct

def write_imu_data(writer, stream_id, imu_msg, timestamp):
    """
    IMUデータをVRSに書き込む

    Args:
        writer: VRSWriter instance
        stream_id: int
        imu_msg: sensor_msgs/Imu
        timestamp: float
    """
    # 加速度データをパック (3 doubles)
    accel_data = struct.pack(
        'ddd',
        imu_msg.linear_acceleration.x,
        imu_msg.linear_acceleration.y,
        imu_msg.linear_acceleration.z
    )

    # VRSに書き込み
    writer.write_data(stream_id, timestamp, accel_data)

def write_imu_config(writer, stream_id):
    """IMU Configuration"""
    config = {
        "sensor_type": "accelerometer",
        "unit": "m/s^2",
        "range": 4.0,  # +/- 4G
        "sample_rate": 250.0,  # Hz
    }
    writer.write_configuration(stream_id, config)
```

### タスク5: VRSファイルから画像を復元

```python
import pyvrs
import numpy as np

def read_image_from_vrs(reader, stream_id, record_index=0):
    """
    VRSファイルから画像データを読み取る

    Args:
        reader: pyvrs.SyncVRSReader
        stream_id: int
        record_index: int (何番目のDataレコードか)

    Returns:
        numpy array (画像データ)
    """
    # 指定ストリームのDataレコードのみ取得
    data_records = [r for r in reader.records()
                   if r.stream_id.numeric_name == stream_id
                   and r.record_type == pyvrs.RecordType.DATA]

    if record_index >= len(data_records):
        raise IndexError("Record index out of range")

    record = data_records[record_index]

    # カスタムブロックから画像データを取得
    if record.custom_blocks:
        image_bytes = record.custom_blocks[0]

        # Configurationから画像サイズを取得（事前に読み込んでおく）
        # width, height, encoding を使ってnumpy配列に変換
        # 例: RGB画像の場合
        # image = np.frombuffer(image_bytes, dtype=np.uint8).reshape(height, width, 3)

        return image_bytes

    return None
```

### タスク6: 特定時間範囲のレコードを抽出

```python
def read_records_in_time_range(reader, stream_id, start_time, end_time):
    """
    指定時間範囲のレコードを抽出

    Args:
        reader: pyvrs.SyncVRSReader
        stream_id: int
        start_time: float (Unix timestamp)
        end_time: float (Unix timestamp)

    Returns:
        list of records
    """
    records = []

    for record in reader.records():
        if record.stream_id.numeric_name != stream_id:
            continue

        if record.record_type != pyvrs.RecordType.DATA:
            continue

        if start_time <= record.timestamp <= end_time:
            records.append(record)

    return records
```

---

## API制約と注意事項

### pyvrs_writer の制約

1. **RecordFormat 未対応**: 現在の実装ではDataLayoutを動的に定義できない
2. **Configuration は JSON 辞書のみ**: 構造化されたバイナリデータは不可
3. **ストリームIDの重複不可**: 同じIDで複数回 `add_stream()` するとエラー

### PyVRS の制約

1. **Linux/macOS のみサポート**: Windows版は開発中
2. **ランダムアクセス制限**: シーケンシャル読み込みのみ効率的
3. **大容量ファイル**: メモリマッピングを使用するため、十分なメモリが必要

### ベストプラクティス

1. **コンテキストマネージャを使用**: `with VRSWriter(...) as writer:` で確実にクローズ
2. **Configuration を最初に書き込む**: Data レコードより前に書き込む
3. **タイムスタンプは単調増加**: 同じストリーム内では時系列順に書き込む
4. **エラーハンドリング**: `try-except` でファイルI/Oエラーをキャッチ

---

## 参考リンク

- [VRS 公式ドキュメント](https://facebookresearch.github.io/vrs/)
- [PyVRS GitHub](https://github.com/facebookresearch/pyvrs)
- [VRS C++ API](https://facebookresearch.github.io/vrs/doxygen/)

---

**作成日:** 2025-11-19
**更新日:** 2025-11-19
**バージョン:** 1.0.0
