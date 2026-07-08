# 実装詳細: RealSense ROSbag → VRS 変換システム

**RealSense D435i ROSbagのRGB-D、IMU、Transform、Device/Sensor Info、OptionsをVRSへ保存・再生するシステムの実装詳細**

---

## 📋 目次

1. [システムアーキテクチャ](#システムアーキテクチャ)
2. [クラス構造とAPI](#クラス構造とapi)
3. [データフロー](#データフロー)
4. [カメラパラメータ取得と保存](#カメラパラメータ取得と保存)
5. [実装済み機能](#実装済み機能)
6. [未対応機能とロードマップ](#未対応機能とロードマップ)
7. [VRS APIの使用方法](#vrs-apiの使用方法)

---

## システムアーキテクチャ

### 全体構成

```mermaid
graph TB
    subgraph "Input: ROSbag"
        RB[ROSbag File<br/>ROS1/ROS2]
        RB_COLOR[Color Image Topic<br/>/device_0/sensor_1/Color_0/image/data]
        RB_DEPTH[Depth Image Topic<br/>/device_0/sensor_0/Depth_0/image/data]
        RB_COLOR_INFO[Color CameraInfo<br/>/device_0/sensor_1/Color_0/info/camera_info]
        RB_DEPTH_INFO[Depth CameraInfo<br/>/device_0/sensor_0/Depth_0/info/camera_info]
        RB_IMU_ACCEL[IMU Accel<br/>/device_0/sensor_2/Accel_0/imu/data]
        RB_IMU_GYRO[IMU Gyro<br/>/device_0/sensor_2/Gyro_0/imu/data]

        RB --> RB_COLOR
        RB --> RB_DEPTH
        RB --> RB_COLOR_INFO
        RB --> RB_DEPTH_INFO
        RB --> RB_IMU_ACCEL
        RB --> RB_IMU_GYRO
    end

    subgraph "Processing Layer"
        READER[AnyReader<br/>rosbags 0.11.3]
        CONVERTER[RosbagToVRSConverter]
        WRITER[VRSWriter]

        RB_COLOR --> READER
        RB_DEPTH --> READER
        RB_COLOR_INFO --> READER
        RB_DEPTH_INFO --> READER
        RB_IMU_ACCEL --> READER
        RB_IMU_GYRO --> READER

        READER --> CONVERTER
        CONVERTER --> WRITER
    end

    subgraph "Output: VRS"
        VRS[VRS File]
        STREAM1001[Stream 1001<br/>Color + K matrix + D coeffs]
        STREAM1002[Stream 1002<br/>Depth + K matrix + D coeffs + depth_scale]
        STREAM1003[Stream 1003<br/>IMU Accelerometer]
        STREAM1004[Stream 1004<br/>IMU Gyroscope]

        WRITER --> VRS
        VRS --> STREAM1001
        VRS --> STREAM1002
        VRS --> STREAM1003
        VRS --> STREAM1004
    end

    subgraph "Verification Layer"
        INSPECTOR[VRS Inspector<br/>inspect_vrs.py]
        VRS_READER[VRSReader]

        VRS --> VRS_READER
        VRS_READER --> INSPECTOR
    end

```

---

## クラス構造とAPI

### クラス図

```mermaid
classDiagram
    class VRSWriter {
        -_writer: pyvrs.writer.VRSWriter
        -_filepath: Path
        -_stream_states: dict[int, StreamState]
        +__init__(filepath: Path, compression: str)
        +add_stream(stream_id: int, flavor: str)
        +write_configuration(stream_id: int, config: dict)
        +write_data(stream_id: int, timestamp: float, data: bytes)
        +is_open() bool
        +close()
        +__enter__() VRSWriter
        +__exit__()
    }

    class VRSReader {
        -_vrs_path: Path
        -_reader: pyvrs.SyncVRSReader
        -_stream_mapping: dict[int, StreamId]
        +__init__(vrs_path: Path)
        +get_stream_ids() list[int]
        +get_record_count(stream_id: int) int
        +read_configuration(stream_id: int) dict
        +read_data_records(stream_id: int) Generator
        +close()
    }

    class RosbagToVRSConverter {
        +rosbag_path: Path
        +vrs_path: Path
        +config: ConverterConfig
        -_stats: dict
        +convert() ConversionResult
        -_open_rosbag() AnyReader
        -_create_streams(writer: VRSWriter)
        -_cache_camera_info(reader: AnyReader)
        -_write_configurations(writer: VRSWriter)
        -_process_messages(reader: AnyReader, writer: VRSWriter)
        -_convert_color_message(msg, timestamp: float) bytes
        -_convert_depth_message(msg, timestamp: float) bytes
    }

    class ConverterConfig {
        +phase: str
        +topic_mapping: dict[str, StreamConfig]
        +compression: str
        +verbose: bool
    }

    class StreamConfig {
        +stream_id: int
        +stream_type: str
        +recordable_type_id: str
        +flavor: str
    }

    class ConversionResult {
        +success: bool
        +input_bag_size: int
        +output_vrs_size: int
        +compression_ratio: float
        +total_messages: int
        +messages_per_stream: dict[int, int]
        +conversion_time_sec: float
        +duration_sec: float
    }

    RosbagToVRSConverter --> VRSWriter : uses
    RosbagToVRSConverter --> ConverterConfig : has
    RosbagToVRSConverter --> ConversionResult : produces
    ConverterConfig --> StreamConfig : contains
```

### 主要クラスの役割

| クラス名 | 役割 | ファイル |
|---------|------|---------|
| `VRSWriter` | VRSファイルへの書き込み（公式 PyVRS writer adapter） | `scripts/vrs_writer.py` |
| `VRSReader` | VRSファイルからの読み込み（PyVRSラッパー） | `scripts/vrs_reader.py:20` |
| `RosbagToVRSConverter` | ROSbag → VRS 変換ロジック | `scripts/rosbag_to_vrs_converter.py:84` |
| `ConverterConfig` | 変換設定（ストリームマッピング、圧縮等） | `scripts/rosbag_to_vrs_converter.py:24` |
| `StreamConfig` | VRSストリーム設定（ID、タイプ、flavor） | `scripts/rosbag_to_vrs_converter.py:24` |

---

## データフロー

### 変換処理のシーケンス

```mermaid
sequenceDiagram
    participant User
    participant CLI as convert_to_vrs.py
    participant Conv as RosbagToVRSConverter
    participant Reader as AnyReader (rosbags)
    participant Writer as VRSWriter
    participant VRS as VRS File

    User->>CLI: ./convert_to_vrs.py input.bag output.vrs
    CLI->>Conv: RosbagToVRSConverter(bag_path, vrs_path, config)
    CLI->>Conv: convert()

    Conv->>Reader: _open_rosbag()
    Reader-->>Conv: AnyReader instance

    Conv->>Writer: VRSWriter(vrs_path)
    Writer-->>Conv: writer instance

    Conv->>Conv: _create_streams(writer)
    Conv->>Writer: add_stream(1001, "Color")
    Conv->>Writer: add_stream(1002, "Depth")

    Conv->>Reader: _cache_camera_info(reader)
    Reader-->>Conv: CameraInfo messages

    Conv->>Conv: _write_configurations(writer)
    Conv->>Writer: write_configuration(1001, color_config)
    Writer->>VRS: Configuration Record (Stream 1001)
    Conv->>Writer: write_configuration(1002, depth_config)
    Writer->>VRS: Configuration Record (Stream 1002)

    loop For each message in ROSbag
        Conv->>Reader: messages()
        Reader-->>Conv: (connection, timestamp, rawdata)
        Conv->>Reader: deserialize(rawdata, msgtype)
        Reader-->>Conv: message object

        alt Color Image
            Conv->>Conv: _convert_color_message(msg, timestamp)
            Conv->>Writer: write_data(1001, timestamp, image_bytes)
            Writer->>VRS: Data Record (Stream 1001)
        else Depth Image
            Conv->>Conv: _convert_depth_message(msg, timestamp)
            Conv->>Writer: write_data(1002, timestamp, image_bytes)
            Writer->>VRS: Data Record (Stream 1002)
        end
    end

    Conv->>Writer: close()
    Writer->>VRS: Finalize index

    Conv-->>CLI: ConversionResult
    CLI-->>User: Success + statistics
```

---

## カメラパラメータ取得と保存

### ROSbag からのカメラパラメータ抽出

#### 1. CameraInfo メッセージの構造

ROSbag内の `sensor_msgs/CameraInfo` メッセージには以下の情報が含まれます：

```python
# sensor_msgs/CameraInfo
header:
  stamp: {sec, nanosec}
  frame_id: str

width: int          # 画像幅
height: int         # 画像高さ
distortion_model: str  # 歪みモデル ("plumb_bob", "Brown Conrady" など)

# カメラ内部パラメータ行列 (3x3, row-major order)
K: [fx,  0, cx,
     0, fy, cy,
     0,  0,  1]

# 歪み係数 (5要素)
D: [k1, k2, p1, p2, k3]

# Rectification matrix (3x3)
R: [...]

# Projection matrix (3x4)
P: [...]

binning_x: int
binning_y: int
roi: RegionOfInterest
```

#### 2. パラメータの取得プロセス

```mermaid
flowchart TD
    A[ROSbag Open] --> B[CameraInfo トピック検索]
    B --> C{トピックが存在?}
    C -->|Yes| D[最初のメッセージを読み取り]
    C -->|No| E[エラー: CameraInfo not found]

    D --> F[CameraInfo.K を取得<br/>fx, fy, cx, cy]
    D --> G[CameraInfo.D を取得<br/>k1, k2, p1, p2, k3]
    D --> H[CameraInfo.distortion_model を取得]
    D --> I[width, height を取得]

    F --> J[Configuration辞書を作成]
    G --> J
    H --> J
    I --> J

    J --> K[VRS Configuration レコードに書き込み]
```

#### 3. 実装コード（抜粋）

```python
# scripts/rosbag_to_vrs_converter.py:172
def _cache_camera_info(self, reader: Any) -> None:
    """CameraInfo メッセージをキャッシュ"""
    camera_info_topics = [
        "/device_0/sensor_1/Color_0/info/camera_info",  # Color
        "/device_0/sensor_0/Depth_0/info/camera_info"   # Depth
    ]

    with reader:
        connections = [x for x in reader.connections
                      if x.topic in camera_info_topics]

        for connection, timestamp, rawdata in reader.messages(connections=connections):
            # rosbags 0.11.3 API
            msg = reader.deserialize(rawdata, connection.msgtype)
            self._stats["camera_info_cache"][connection.topic] = msg
```

```python
# scripts/rosbag_to_vrs_converter.py:211
def _write_color_configuration(self, writer: VRSWriter, ...) -> None:
    """Color ストリームの Configuration レコードを書き込み"""
    camera_info = self._stats["camera_info_cache"].get(camera_info_topic)

    config_data = {
        "width": int(camera_info.width),
        "height": int(camera_info.height),
        "encoding": "rgb8",
        "camera_k": list(camera_info.K),  # [fx, 0, cx, 0, fy, cy, 0, 0, 1]
        "camera_d": list(camera_info.D),  # [k1, k2, p1, p2, k3]
        "distortion_model": camera_info.distortion_model,
        "frame_id": camera_info.header.frame_id
    }

    writer.write_configuration(stream_id, config_data)
```

### VRS への保存形式

#### Configuration レコードの構造

```json
{
  "stream_id": 1001,
  "record_type": "Configuration",
  "data": {
    "width": 640,
    "height": 480,
    "encoding": "rgb8",
    "camera_k": [616.52, 0.0, 315.87, 0.0, 616.65, 244.28, 0.0, 0.0, 1.0],
    "camera_d": [0.0, 0.0, 0.0, 0.0, 0.0],
    "distortion_model": "Brown Conrady",
    "frame_id": ""
  }
}
```

---

## 実装済み機能

### ✅ Color Stream (Stream ID: 1001)

**対応ROSbagトピック:**
- `/device_0/sensor_1/Color_0/image/data` (sensor_msgs/Image)
- `/device_0/sensor_1/Color_0/info/camera_info` (sensor_msgs/CameraInfo)

**保存データ:**
- RGB画像データ (bytes)
- カメラ内部パラメータ (K matrix: 3x3)
- 歪み係数 (D vector: 5 elements)
- 歪みモデル (distortion_model: str)
- 解像度 (width, height)

**実装ファイル:**
- `scripts/rosbag_to_vrs_converter.py:211` - `_write_color_configuration()`
- `scripts/rosbag_to_vrs_converter.py:260` - `_process_color_message()`

### ✅ Depth Stream (Stream ID: 1002)

**対応ROSbagトピック:**
- `/device_0/sensor_0/Depth_0/image/data` (sensor_msgs/Image)
- `/device_0/sensor_0/Depth_0/info/camera_info` (sensor_msgs/CameraInfo)

**保存データ:**
- Depth画像データ (bytes, 16UC1)
- カメラ内部パラメータ (K matrix: 3x3)
- 歪み係数 (D vector: 5 elements)
- 歪みモデル (distortion_model: str)
- 解像度 (width, height)
- **Depth scale** (0.001 = 1mm単位 → メートル変換)

**実装ファイル:**
- `scripts/rosbag_to_vrs_converter.py:234` - `_write_depth_configuration()`
- `scripts/rosbag_to_vrs_converter.py:273` - `_process_depth_message()`

---

### IMU / Transform / Device Info / Options

`create_rgbd_imu_config()` は Color/Depth に加えて以下の stream を含みます。

| Stream ID | 種別 | 内容 |
|----------:|------|------|
| 1003 | IMU Accel | `sensor_msgs/Imu.linear_acceleration` を double x3 として保存 |
| 1004 | IMU Gyro | `sensor_msgs/Imu.angular_velocity` を double x3 として保存 |
| 1005, 1006 | Transform | Depth/Color extrinsic configuration |
| 2001 | Device Info | device key-value metadata |
| 2002-2004 | Sensor Info | sensor module metadata |
| 2005 | Options | sensor option value/description metadata |

## 未対応機能とロードマップ

### IR (Infrared) Stream

#### 必要な構造

**対応ROSbagトピック:**
- `/device_0/sensor_0/Infrared_1/image/data` (sensor_msgs/Image)
- `/device_0/sensor_0/Infrared_2/image/data` (sensor_msgs/Image)

**Stream 定義:**

```python
STREAM_ID_IR1 = 1005
STREAM_ID_IR2 = 1006

StreamConfig(
    stream_id=1005,
    stream_type="ir",
    recordable_type_id="EyeCamera",  # or ForwardCamera
    flavor="RealSense_D435i_IR1"
)
```

**Configuration レコード:**

```json
{
  "width": 1280,
  "height": 720,
  "encoding": "mono8",
  "camera_k": [...],
  "camera_d": [...],
  "distortion_model": "Brown Conrady",
  "frame_id": "infra1_optical_frame"
}
```

### 実装優先順位

| 機能 | Phase | 優先度 | 理由 |
|-----|-------|-------|------|
| Color + Depth | 現行 | ✅ 完了 | 最も基本的なRGB-D機能 |
| IMU (Accel/Gyro) | 現行 | ✅ 完了 | SLAM/VIO に必須 |
| TF / Device / Sensor / Options | 現行 | ✅ 完了 | 再生時の周辺情報 |
| IR (Infrared) | 今後 | 🟡 中 | ステレオマッチングに有用 |
| per-frame Metadata | 今後 | 🟢 低 | 追加メタデータ |

---

## VRS APIの使用方法

### 公式 PyVRS writer adapter (書き込み)

```python
from scripts.vrs_writer import VRSWriter

# VRSファイルを開く
with VRSWriter("output.vrs", compression="lz4") as writer:
    # ストリームを追加
    writer.add_stream(1001, "RealSense_Color")

    # Configuration レコードを書き込み
    config = {
        "width": 640,
        "height": 480,
        "camera_k": [fx, 0, cx, 0, fy, cy, 0, 0, 1]
    }
    writer.write_configuration(1001, config)

    # Data レコードを書き込み
    timestamp = 1234567890.123
    image_bytes = b'...'  # RGB画像データ
    writer.write_data(1001, timestamp, image_bytes)
```

### PyVRS (読み込み)

```python
import pyvrs

# VRSファイルを開く
reader = pyvrs.SyncVRSReader("output.vrs")
reader.open()

# ストリーム一覧を取得
streams = reader.get_streams()

# Configuration レコードを読み取り
config_records = [r for r in reader.records() if r.record_type == pyvrs.RecordType.CONFIGURATION]

# Data レコードを読み取り
for record in reader.records():
    if record.record_type == pyvrs.RecordType.DATA:
        # メタデータブロックを取得
        metadata = record.metadata_blocks[0] if record.metadata_blocks else {}

        # カスタムブロック（画像データなど）を取得
        if record.image_blocks:
            data = record.image_blocks[0].tobytes()
        elif record.custom_blocks:
            data = record.custom_blocks[0]
        else:
            data = b""
```

---

## 技術的な制約と注意事項

### 1. rosbags API の変更

- **rosbags 0.9.x以前**: `Reader.deserialize()` メソッドが存在
- **rosbags 0.11.3**: `AnyReader.deserialize()` を使用
- **対応**: `scripts/rosbag_to_vrs_converter.py` で `AnyReader` を使用

### 2. CameraInfo 属性名の大文字化

- **ROSメッセージ定義**: `K`, `D`, `R`, `P` (大文字)
- **rosbags デシリアライズ後**: `camera_info.K`, `camera_info.D` (大文字のまま)
- **注意**: 小文字 `k`, `d` ではアクセスできない

### 3. 公式 PyVRS writer adapter の制限

- **現状**: PyPI `vrs==1.2.2` の writer module は direct import 時に `RecordFormat` export 欠落で失敗するため、`scripts.vrs_writer.load_official_writer_backend()` で必要な native symbols と旧 compression alias を補正している。
- **Recordable type**: 公式 writer は汎用 recordable writer ではなく登録済み factory のみを作成できる。本リポジトリでは `sample_with_image` factory を使い、logical stream id/config は stream tags、payload は image block に保存する compatibility encoding を採用している。
- **影響**: `scripts.vrs_reader.VRSReader` では stream id、configuration、timestamp、payload を roundtrip できるが、外部 VRS consumer 向けの意味論的 recordable 型は未保証。

---

## まとめ

### 現在の実装状況

| 機能 | ステータス | 実装場所 |
|-----|----------|---------|
| Color Image + K/D | ✅ 完了 | `rosbag_to_vrs_converter.py:211` |
| Depth Image + K/D + depth_scale | ✅ 完了 | `rosbag_to_vrs_converter.py:234` |
| ROSbag同等の情報再生 | ✅ 達成 | Configuration レコードに保存 |
| IMU (Accel/Gyro) | ✅ 完了 | `create_rgbd_imu_config()` |
| Transform / Device / Sensor / Options | ✅ 完了 | `create_rgbd_imu_config()` |
| IR (Infrared) | 今後 | ロードマップあり |

### pyvrs経由でのRGB-D + IMU読み込み

**現状:**
- ✅ RGB: 読み込み可能（PyVRS経由）
- ✅ Depth: 読み込み可能（PyVRS経由）
- ✅ IMU: 読み込み可能（PyVRS経由）
- ✅ Transform / Device / Sensor / Options: configuration として読み込み可能
- 未対応: IR と per-frame metadata は VRSファイルに保存されていない

詳細は本ドキュメントの「未対応機能とロードマップ」セクションを参照してください。

---

**作成日:** 2025-11-19
**作成者:** Claude (Sonnet 4.5)
**更新日:** 2026-07-08
**バージョン:** 1.1.0
