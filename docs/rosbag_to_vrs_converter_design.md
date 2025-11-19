# ROSbag to VRS Converter 設計書

**作成日**: 2025年11月19日
**対象**: RealSense D435i ROSbag → VRS変換実装
**参照**: `docs/rosbag_vrs_mapping_design.md`

---

## 1. 処理フロー

```
1. ROSbagファイルを開く（rosbags-py使用）
2. VRSファイルを作成（pyvrs_writer使用）
3. マッピング仕様に基づいてストリームを作成
4. 各ストリームのConfigurationレコードを書き込み
5. 全メッセージを時系列順に読み込み、対応するVRSストリームにDataレコードとして書き込み
6. ファイルをクローズ
```

### Phase 4A実装範囲（必須）

- Stream 1001: Color Image (RGB)
- Stream 1002: Depth Image

### Phase 4B実装範囲（推奨）

- Stream 2001: IMU Accelerometer
- Stream 2002: IMU Gyroscope

---

## 2. モジュール設計

### 2.1 RosbagToVRSConverter (`scripts/rosbag_to_vrs_converter.py`)

#### クラス: `RosbagToVRSConverter`

**責務**: ROSbag→VRS変換のメインロジック

#### コンストラクタ

```python
def __init__(self, rosbag_path: Path, vrs_path: Path, config: ConverterConfig)
```

**引数**:
- `rosbag_path`: 入力ROSbagファイルパス
- `vrs_path`: 出力VRSファイルパス
- `config`: 変換設定（トピックマッピング、実装phase）

#### メソッド

##### `convert() -> ConversionResult`

変換処理のメインエントリーポイント

**処理フロー**:
1. ROSbagを開く
2. トピック情報を検証
3. VRSWriterを初期化
4. ストリームを作成
5. Configurationレコードを書き込み
6. メッセージを時系列順に処理
7. 統計情報を返却

**戻り値**: `ConversionResult`（変換統計情報）

##### `_create_streams() -> None`

マッピング設定に基づきVRSストリームを作成

**Phase 4A対応ストリーム**:
- Stream 1001: Color Image
- Stream 1002: Depth Image

**Phase 4B対応ストリーム**:
- Stream 2001: IMU Accel
- Stream 2002: IMU Gyro

##### `_write_configurations() -> None`

各ストリームのConfigurationレコードを書き込み

**Color Image Configuration**:
```python
{
    "width": 1920,
    "height": 1080,
    "encoding": "rgb8",
    "camera_k": [fx, 0, cx, 0, fy, cy, 0, 0, 1],  # 9要素
    "camera_d": [k1, k2, p1, p2, k3],  # 5要素
    "distortion_model": "plumb_bob"
}
```

**Depth Image Configuration**:
```python
{
    "width": 1280,
    "height": 720,
    "encoding": "16UC1",
    "camera_k": [fx, 0, cx, 0, fy, cy, 0, 0, 1],
    "camera_d": [k1, k2, p1, p2, k3],
    "distortion_model": "plumb_bob",
    "depth_scale": 0.001  # mm → meters
}
```

##### `_process_messages() -> None`

ROSbagメッセージを時系列順に処理

**処理対象トピック（Phase 4A）**:
- `/device_0/sensor_1/Color_0/image/data`
- `/device_0/sensor_0/Depth_0/image/data`
- `/device_0/sensor_1/Color_0/camera_info` (初回のみ、Configuration用)
- `/device_0/sensor_0/Depth_0/camera_info` (初回のみ、Configuration用)

**処理対象トピック（Phase 4B追加）**:
- `/device_0/sensor_2/Accel_0/imu/data`
- `/device_0/sensor_2/Gyro_0/imu/data`

##### `_convert_color_message(msg: ImageMessage, camera_info: CameraInfoMessage) -> Tuple[Dict, bytes]`

Color Imageメッセージ変換

**入力**: `sensor_msgs/msg/Image` (rgb8/bgr8)
**出力**:
- DataLayout辞書: `{"timestamp": float, "frame_id": str}`
- Image bytes: width × height × 3 bytes

##### `_convert_depth_message(msg: ImageMessage, camera_info: CameraInfoMessage) -> Tuple[Dict, bytes]`

Depth Imageメッセージ変換

**入力**: `sensor_msgs/msg/Image` (16UC1)
**出力**:
- DataLayout辞書: `{"timestamp": float, "frame_id": str}`
- Image bytes: width × height × 2 bytes (uint16)

##### `_convert_imu_accel_message(msg: ImuMessage) -> Dict`

IMU Accelerometerメッセージ変換（Phase 4B）

**入力**: `sensor_msgs/msg/Imu`
**出力**:
```python
{
    "timestamp": float,
    "linear_acceleration": {"x": float, "y": float, "z": float},
    "frame_id": str
}
```

##### `_convert_imu_gyro_message(msg: ImuMessage) -> Dict`

IMU Gyroscopeメッセージ変換（Phase 4B）

**入力**: `sensor_msgs/msg/Imu`
**出力**:
```python
{
    "timestamp": float,
    "angular_velocity": {"x": float, "y": float, "z": float},
    "frame_id": str
}
```

---

## 3. データクラス設計

### 3.1 ConverterConfig

```python
@dataclass
class ConverterConfig:
    """変換設定"""
    topic_mapping: Dict[str, StreamConfig]
    phase: str  # "4A", "4B", "4C"
    compression: str = "lz4"  # "none", "lz4", "zstd"
    verbose: bool = False
```

### 3.2 StreamConfig

```python
@dataclass
class StreamConfig:
    """ストリーム設定"""
    stream_id: int
    stream_type: str  # "color", "depth", "imu_accel", "imu_gyro"
    recordable_type_id: str  # "ForwardCamera", "MotionSensor"
    flavor: str
```

### 3.3 ConversionResult

```python
@dataclass
class ConversionResult:
    """変換結果統計"""
    input_bag_size: int  # bytes
    output_vrs_size: int  # bytes
    compression_ratio: float
    total_messages: int
    messages_per_stream: Dict[int, int]  # stream_id -> count
    duration_sec: float
    conversion_time_sec: float
```

---

## 4. トピックマッピング定義（Phase 4A）

```python
PHASE_4A_MAPPING = {
    "/device_0/sensor_1/Color_0/image/data": StreamConfig(
        stream_id=1001,
        stream_type="color",
        recordable_type_id="ForwardCamera",
        flavor="RealSense_D435i_Color|id:1001"
    ),
    "/device_0/sensor_0/Depth_0/image/data": StreamConfig(
        stream_id=1002,
        stream_type="depth",
        recordable_type_id="ForwardCamera",
        flavor="RealSense_D435i_Depth|id:1002"
    ),
}
```

---

## 5. トピックマッピング定義（Phase 4B追加）

```python
PHASE_4B_MAPPING = {
    **PHASE_4A_MAPPING,
    "/device_0/sensor_2/Accel_0/imu/data": StreamConfig(
        stream_id=2001,
        stream_type="imu_accel",
        recordable_type_id="MotionSensor",
        flavor="RealSense_D435i_IMU_Accel|id:2001"
    ),
    "/device_0/sensor_2/Gyro_0/imu/data": StreamConfig(
        stream_id=2002,
        stream_type="imu_gyro",
        recordable_type_id="MotionSensor",
        flavor="RealSense_D435i_IMU_Gyro|id:2002"
    ),
}
```

---

## 6. エラーハンドリング

### 6.1 入力検証エラー

- **ROSbagファイル不存在**: `FileNotFoundError`
- **ROSbag読み込み失敗**: `RosbagReadError`
- **必須トピック不在**: `MissingTopicError`

### 6.2 変換エラー

- **画像サイズ不一致**: `ImageSizeMismatchError`
- **エンコーディング未サポート**: `UnsupportedEncodingError`
- **VRS書き込み失敗**: `VRSWriteError`

### 6.3 エラー対処方針

- **暗黙的fallback禁止**: エラー発生時は明示的な例外を送出
- **ロギング**: 全エラーをログに記録
- **クリーンアップ**: 失敗時は部分的VRSファイルを削除

---

## 7. パフォーマンス要件

- **メモリ使用量**: 画像1フレーム分のメモリのみ使用（ストリーミング処理）
- **処理速度**: 実時間の5倍以上（1分のROSbag → 12秒以内で変換完了）
- **ファイルサイズ**: ROSbagの50-70%を目標（lz4圧縮時）

---

## 8. テスト戦略

### 8.1 単体テスト

- ConverterConfig初期化
- StreamConfig検証
- メッセージ変換関数（各型）
- エラーハンドリング

### 8.2 統合テスト

- サンプルROSbag変換（Phase 4A）
- 変換後VRSファイル検証（ストリーム数、レコード数）
- 変換後VRSファイル読み取り（C++ VRS Reader）

### 8.3 E2Eテスト

- 実ROSbag変換（d435i_sample_data.zip解凍後）
- VRSファイルサイズ検証
- データ完全性検証（ピクセル値、タイムスタンプ）

---

## 9. DRY/KISS/SOLID原則適用

### DRY (Don't Repeat Yourself)

- 画像メッセージ変換ロジックを `_convert_image_message_base()` として共通化
- Configuration書き込みロジックを `_write_configuration_record()` として共通化

### KISS (Keep It Simple, Stupid)

- 1クラス1責務（Converter、Config、Result）
- メソッドは1画面に収まる長さ（20行以内目標）

### SOLID原則

- **Single Responsibility**: Converterは変換のみ、ファイルI/Oは他モジュール
- **Open/Closed**: 新ストリーム追加時は`StreamConfig`追加のみ
- **Liskov Substitution**: N/A（継承なし）
- **Interface Segregation**: N/A（単一インターフェース）
- **Dependency Inversion**: VRSWriter、RosbagReaderはインターフェース経由で使用

---

## 10. 次ステップ（実装順序）

1. **Phase 4.1完了**: 本設計書作成完了
2. **Phase 4.2**: テストケース作成（TDD RED）
3. **Phase 4.3**: Converter実装（TDD GREEN）
4. **Phase 4.4**: CLIスクリプト作成
5. **Phase 5**: VRS Inspector/Player実装
6. **Phase 6**: 統合テスト

---

**作成者**: Claude (Sonnet 4.5)
**バージョン**: 1.0
**最終更新**: 2025-11-19 10:06 UTC
