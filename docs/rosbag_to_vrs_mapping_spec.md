# ROSbag to VRS データマッピング仕様

**作成日:** 2025-11-19
**バージョン:** 1.0

## 概要

このドキュメントは、RealSense D435iセンサーから記録されたROSbag形式のデータをVRS (Virtual Reality Stream) 形式に変換する際のデータマッピング仕様を定義します。

## ストリーム設計

| VRS Stream ID | センサー種別 | ROSbagトピック | データ型 | サンプリングレート |
|--------------|------------|---------------|--------|------------------|
| 1001 | RGB Camera | /device_0/sensor_1/Color_0/image/data | sensor_msgs/msg/Image | ~30 Hz |
| 1002 | Depth Camera | /device_0/sensor_0/Depth_0/image/data | sensor_msgs/msg/Image | ~30 Hz |
| 2001 | IMU Accel | /device_0/sensor_2/Accel_0/imu/data | sensor_msgs/msg/Imu | ~63-250 Hz |
| 2002 | IMU Gyro | /device_0/sensor_2/Gyro_0/imu/data | sensor_msgs/msg/Imu | ~200-400 Hz |

**Stream ID 割り当てルール:**
- 1000番台: カメラ系センサー（RGB, Depth, IR等）
- 2000番台: IMUセンサー（Accel, Gyro）
- 3000番台以降: 将来の拡張用（予約）

## Configurationレコード内容

各ストリームの初期化時に1回だけ書き込まれるConfiguration recordの内容を定義します。

### RGB Camera (Stream 1001)

```json
{
  "sensor_type": "RGB Camera",
  "stream_id": 1001,
  "width": 640,
  "height": 480,
  "encoding": "rgb8",
  "frame_id": "camera_color_optical_frame",
  "topic": "/device_0/sensor_1/Color_0/image/data"
}
```

**フィールド説明:**
- `width`: 画像幅（ピクセル）
- `height`: 画像高さ（ピクセル）
- `encoding`: 画像エンコーディング（RGB8 / BGR8 等）
- `frame_id`: ROSフレームID（座標系識別子）

### Depth Camera (Stream 1002)

```json
{
  "sensor_type": "Depth Camera",
  "stream_id": 1002,
  "width": 640,
  "height": 480,
  "encoding": "16UC1",
  "depth_scale": 0.001,
  "frame_id": "camera_depth_optical_frame",
  "topic": "/device_0/sensor_0/Depth_0/image/data"
}
```

**フィールド説明:**
- `width`: 画像幅（ピクセル）
- `height`: 画像高さ（ピクセル）
- `encoding`: 深度エンコーディング（16UC1 = 16bit unsigned single channel）
- `depth_scale`: 深度値をメートルに変換する係数（通常 0.001 = 1mm単位）
- `frame_id`: ROSフレームID

### IMU Accelerometer (Stream 2001)

```json
{
  "sensor_type": "IMU Accelerometer",
  "stream_id": 2001,
  "sensor_name": "Accel",
  "frame_id": "camera_accel_optical_frame",
  "unit": "m/s^2",
  "topic": "/device_0/sensor_2/Accel_0/imu/data"
}
```

**フィールド説明:**
- `sensor_name`: センサー識別名（"Accel"）
- `frame_id`: ROSフレームID
- `unit`: 測定単位（m/s²）

### IMU Gyroscope (Stream 2002)

```json
{
  "sensor_type": "IMU Gyroscope",
  "stream_id": 2002,
  "sensor_name": "Gyro",
  "frame_id": "camera_gyro_optical_frame",
  "unit": "rad/s",
  "topic": "/device_0/sensor_2/Gyro_0/imu/data"
}
```

**フィールド説明:**
- `sensor_name`: センサー識別名（"Gyro"）
- `frame_id`: ROSフレームID
- `unit`: 測定単位（rad/s）

## Dataレコード内容

各ストリームで継続的に書き込まれるData recordの内容を定義します。

### 画像データ (Stream 1001: RGB Camera)

**データ構造:**
```
timestamp: double (seconds, relative to bag start time)
image_data: bytes (raw image data or compressed)
```

**詳細:**
- `timestamp`: VRSタイムスタンプ（ROSbag開始時刻からの相対時刻、秒単位の浮動小数点数）
- `image_data`: 生画像バイト列
  - RGB8の場合: width × height × 3 バイト
  - オプション: JPEG/PNG圧縮データ（将来の拡張）

**データサイズ例:**
- 640×480 RGB8: 921,600 バイト/フレーム
- 1920×1080 RGB8: 6,220,800 バイト/フレーム

### 画像データ (Stream 1002: Depth Camera)

**データ構造:**
```
timestamp: double (seconds, relative to bag start time)
image_data: bytes (16-bit depth values)
```

**詳細:**
- `timestamp`: VRSタイムスタンプ（ROSbag開始時刻からの相対時刻）
- `image_data`: 16bit深度値配列
  - 16UC1の場合: width × height × 2 バイト
  - 各ピクセルの深度値 × depth_scale = 実際の距離（メートル）

**データサイズ例:**
- 640×480 16UC1: 614,400 バイト/フレーム

### IMUデータ (Stream 2001: Accelerometer)

**データ構造:**
```
timestamp: double (seconds, relative to bag start time)
linear_acceleration_x: float (m/s^2)
linear_acceleration_y: float (m/s^2)
linear_acceleration_z: float (m/s^2)
```

**詳細:**
- `timestamp`: VRSタイムスタンプ
- `linear_acceleration_[x,y,z]`: 加速度ベクトル成分（m/s²）

**データサイズ:**
- 1タイムスタンプ（8バイト）+ 3×float（12バイト）= 20バイト/サンプル

### IMUデータ (Stream 2002: Gyroscope)

**データ構造:**
```
timestamp: double (seconds, relative to bag start time)
angular_velocity_x: float (rad/s)
angular_velocity_y: float (rad/s)
angular_velocity_z: float (rad/s)
```

**詳細:**
- `timestamp`: VRSタイムスタンプ
- `angular_velocity_[x,y,z]`: 角速度ベクトル成分（rad/s）

**データサイズ:**
- 1タイムスタンプ（8バイト）+ 3×float（12バイト）= 20バイト/サンプル

## タイムスタンプ変換

### ROSタイムスタンプ形式

ROSbagのタイムスタンプは以下の形式で記録されています：
- `rospy.Time.to_sec()`: Unixエポック（1970-01-01 00:00:00 UTC）からの秒数（浮動小数点数）
- 精度: ナノ秒（10^-9秒）

### VRSタイムスタンプ形式

VRSでは相対時刻を使用します：
```
VRS_timestamp = ROS_timestamp - bag_start_timestamp
```

**変換ロジック:**
1. ROSbagを開き、最初のメッセージのタイムスタンプを `bag_start_timestamp` として記録
2. 各メッセージのタイムスタンプから `bag_start_timestamp` を減算
3. 結果を秒単位の浮動小数点数としてVRSに記録

**例:**
```
bag_start_timestamp = 1234567890.123456 (秒)
message_timestamp   = 1234567890.156789 (秒)
VRS_timestamp       = 0.033333 (秒) ≈ 33.3 ms
```

## データ型マッピング

### sensor_msgs/msg/Image → VRS Image Data

| ROS Field | Type | VRS Mapping |
|-----------|------|-------------|
| header.stamp | Time | timestamp (double, relative) |
| height | uint32 | Configuration record: height |
| width | uint32 | Configuration record: width |
| encoding | string | Configuration record: encoding |
| is_bigendian | uint8 | (省略、little-endian前提) |
| step | uint32 | (計算可能: width × bytes_per_pixel) |
| data | uint8[] | Data record: image_data (bytes) |

### sensor_msgs/msg/Imu → VRS IMU Data

| ROS Field | Type | VRS Mapping (Accel) | VRS Mapping (Gyro) |
|-----------|------|---------------------|--------------------|
| header.stamp | Time | timestamp (double) | timestamp (double) |
| linear_acceleration.x | float64 | linear_acceleration_x | (使用しない) |
| linear_acceleration.y | float64 | linear_acceleration_y | (使用しない) |
| linear_acceleration.z | float64 | linear_acceleration_z | (使用しない) |
| angular_velocity.x | float64 | (使用しない) | angular_velocity_x |
| angular_velocity.y | float64 | (使用しない) | angular_velocity_y |
| angular_velocity.z | float64 | (使用しない) | angular_velocity_z |
| orientation | Quaternion | (省略、生データのみ記録) |
| covariances | float64[9] | (省略) |

## 実装上の注意事項

### メモリ効率

- 画像データは大容量（640×480 RGB: 約900KB/フレーム）
- ストリーミング処理を推奨（全データをメモリに展開しない）
- VRSのlz4/zstd圧縮を活用

### 時刻同期

- RealSense D435iは各センサーが独立したタイムスタンプを持つ
- VRSでは各ストリームが独立したタイムスタンプを保持可能
- 時刻同期が必要な場合は、後処理で補間を実施

### エラーハンドリング

- トピック名が存在しない場合: 警告を出力してスキップ
- データ破損の場合: 該当フレーム/サンプルをスキップし、ログに記録
- タイムスタンプの逆行: エラーとして報告（VRSは時系列順を期待）

## テストケース

以下のケースでマッピングを検証すること：

1. **正常系:**
   - 全トピックが存在するROSbag
   - 30秒間の連続記録
   - 変換後のVRSファイルが再生可能

2. **異常系:**
   - トピック欠落（例: Depthトピックなし）→ RGBのみ変換
   - 空のROSbag → エラーメッセージ表示
   - タイムスタンプ異常 → 該当メッセージをスキップ

3. **境界値:**
   - 1フレームのみのROSbag
   - 1時間以上の長時間記録
   - 異なる解像度（1920×1080等）

## 参考資料

- **VRS公式ドキュメント**: https://facebookresearch.github.io/vrs/
- **sensor_msgs/Image**: https://docs.ros.org/en/api/sensor_msgs/html/msg/Image.html
- **sensor_msgs/Imu**: https://docs.ros.org/en/api/sensor_msgs/html/msg/Imu.html
- **RealSense ROS Wrapper**: https://github.com/IntelRealSense/realsense-ros

---

**変更履歴:**
- 2025-11-19: 初版作成
