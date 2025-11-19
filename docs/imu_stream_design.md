# IMUストリーム設計仕様

**日付:** 2025-11-19
**バージョン:** 1.0.0
**対象:** RealSense D435i IMUデータ（Accelerometer + Gyroscope）

---

## 1. 概要

本ドキュメントは、RealSense D435i IMUデータ（加速度計・ジャイロスコープ）をVRS形式に変換するためのストリーム設計仕様を定義します。

### 目的

- ROSbag形式のIMUデータ（sensor_msgs/msg/Imu）をVRS形式に変換
- ROSbagと同等の情報再生機能を提供（3軸データ、タイムスタンプ、センサー情報）
- Meta VRSエコシステムとの互換性確保

---

## 2. ROSbagデータ構造

### 2.1 ROSbagトピック

| トピック名 | メッセージ型 | 説明 | サンプリングレート（実測） |
|-----------|------------|------|-------------------------|
| `/device_0/sensor_2/Accel_0/imu/data` | sensor_msgs/msg/Imu | 加速度計データ | 約44 Hz |
| `/device_0/sensor_2/Gyro_0/imu/data` | sensor_msgs/msg/Imu | ジャイロスコープデータ | 約55 Hz |
| `/device_0/sensor_2/Accel_0/imu_intrinsic` | realsense_msgs/msg/ImuIntrinsic | 加速度計内部パラメータ | 1回（初回のみ） |
| `/device_0/sensor_2/Gyro_0/imu_intrinsic` | realsense_msgs/msg/ImuIntrinsic | ジャイロ内部パラメータ | 1回（初回のみ） |

### 2.2 sensor_msgs/msg/Imu メッセージ構造

```
std_msgs/Header header
  uint32 seq
  time stamp
  string frame_id

geometry_msgs/Quaternion orientation        # 未使用（0, 0, 0, 0）
float64[9] orientation_covariance           # 未使用（全て0）

geometry_msgs/Vector3 angular_velocity      # ジャイロのみ使用
  float64 x
  float64 y
  float64 z
float64[9] angular_velocity_covariance      # 未使用（全て0）

geometry_msgs/Vector3 linear_acceleration   # 加速度計のみ使用
  float64 x
  float64 y
  float64 z
float64[9] linear_acceleration_covariance   # 未使用（全て0）
```

### 2.3 実測データ例

**Accelerometer:**
- Frame ID: `0`（数値）
- Linear Acceleration: `x=5.325, y=-71.540, z=-28.096` (m/s²)
- Angular Velocity: `x=0.000, y=0.000, z=0.000`（未使用）
- Orientation: `x=0.000, y=0.000, z=0.000, w=0.000`（未使用）

**Gyroscope:**
- Frame ID: `0`（数値）
- Angular Velocity: `x=-0.171, y=0.052, z=0.101` (rad/s)
- Linear Acceleration: `x=0.000, y=0.000, z=0.000`（未使用）
- Orientation: `x=0.000, y=0.000, z=0.000, w=0.000`（未使用）

---

## 3. VRSストリーム設計

### 3.1 ストリームID割り当て

| ストリームID | Flavor名 | 説明 | データソース |
|------------|---------|------|------------|
| 1001 | RealSense_D435i_Color | RGB画像 | /device_0/sensor_1/Color_0/image/data |
| 1002 | RealSense_D435i_Depth | Depth画像 | /device_0/sensor_0/Depth_0/image/data |
| 1003 | RealSense_D435i_Accel | 加速度計 | /device_0/sensor_2/Accel_0/imu/data |
| 1004 | RealSense_D435i_Gyro | ジャイロスコープ | /device_0/sensor_2/Gyro_0/imu/data |

### 3.2 Configuration レコード構造

#### Stream 1003 (Accelerometer)

```json
{
  "sensor_type": "accelerometer",
  "frame_id": "0",
  "unit": "m/s^2",
  "sample_rate": 44.0,
  "axes": ["x", "y", "z"],
  "range": null,
  "noise_variances": [0.0, 0.0, 0.0],
  "bias_variances": [0.0, 0.0, 0.0]
}
```

#### Stream 1004 (Gyroscope)

```json
{
  "sensor_type": "gyroscope",
  "frame_id": "0",
  "unit": "rad/s",
  "sample_rate": 55.0,
  "axes": ["x", "y", "z"],
  "range": null,
  "noise_variances": [0.0, 0.0, 0.0],
  "bias_variances": [0.0, 0.0, 0.0]
}
```

### 3.3 Data レコード構造

#### データフォーマット

- **データ型:** Custom binary block
- **サイズ:** 24 bytes (3 × 8 bytes double)
- **エンコーディング:** Little-endian, IEEE 754 double precision
- **構造:** `struct.pack('<ddd', x, y, z)`

#### Stream 1003 (Accelerometer)

```
Timestamp: <Unix timestamp (float)>
Data: [24 bytes]
  - x: double (8 bytes) - X軸加速度 (m/s²)
  - y: double (8 bytes) - Y軸加速度 (m/s²)
  - z: double (8 bytes) - Z軸加速度 (m/s²)
```

#### Stream 1004 (Gyroscope)

```
Timestamp: <Unix timestamp (float)>
Data: [24 bytes]
  - x: double (8 bytes) - X軸角速度 (rad/s)
  - y: double (8 bytes) - Y軸角速度 (rad/s)
  - z: double (8 bytes) - Z軸角速度 (rad/s)
```

---

## 4. タイムスタンプ変換

### 4.1 ROSタイムスタンプ → VRSタイムスタンプ

```python
# ROSタイムスタンプ（nanoseconds）
ros_timestamp_ns = msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec

# Unix timestamp（float, seconds）
unix_timestamp = ros_timestamp_ns / 1_000_000_000.0
```

---

## 5. 実装方針

### 5.1 Phase 4B: IMU変換実装の流れ

1. **手順4B.1:** IMUストリーム設計（本ドキュメント）✓
2. **手順4B.2:** IMU Configurationレコード仕様策定
3. **手順4B.3:** IMU Dataレコード仕様策定（データ構造・パッキング）
4. **手順4B.4:** VRSWriter にIMU Configuration書き込み機能追加
5. **手順4B.5:** VRSWriter にIMU Data書き込み機能追加（TDD: RED）
6. **手順4B.6:** VRSWriter IMU機能実装（TDD: GREEN）
7. **手順4B.7:** RosbagToVRSConverter にIMU変換ロジック追加
8. **手順4B.8:** IMU変換テストケース作成
9. **手順4B.9:** IMU変換テスト実行・修正（TDD: GREEN）
10. **手順4B.10:** VRSReader でIMU読み込み動作確認
11. **手順4B.11:** inspect_vrs.py にIMUストリーム表示機能追加
12. **手順4B.12:** 実ROSbag（d435i_walking.bag）でIMU変換・検証テスト
13. **手順4B.13:** コミット・プッシュ

### 5.2 RosbagToVRSConverter 実装メソッド

```python
def _convert_imu_accel_message(
    self,
    msg: sensor_msgs__msg__Imu,
    timestamp: float
) -> bytes:
    """
    加速度計メッセージをVRSバイナリデータに変換

    Args:
        msg: sensor_msgs/Imu メッセージ
        timestamp: Unix timestamp

    Returns:
        24 bytes packed data (3 doubles)
    """
    import struct
    return struct.pack(
        '<ddd',
        msg.linear_acceleration.x,
        msg.linear_acceleration.y,
        msg.linear_acceleration.z
    )

def _convert_imu_gyro_message(
    self,
    msg: sensor_msgs__msg__Imu,
    timestamp: float
) -> bytes:
    """
    ジャイロスコープメッセージをVRSバイナリデータに変換

    Args:
        msg: sensor_msgs/Imu メッセージ
        timestamp: Unix timestamp

    Returns:
        24 bytes packed data (3 doubles)
    """
    import struct
    return struct.pack(
        '<ddd',
        msg.angular_velocity.x,
        msg.angular_velocity.y,
        msg.angular_velocity.z
    )
```

### 5.3 StreamConfig 更新

```python
# 加速度計ストリーム
StreamConfig(
    ros_topic="/device_0/sensor_2/Accel_0/imu/data",
    vrs_stream_id=1003,
    vrs_flavor="RealSense_D435i_Accel",
    ros_msg_type="sensor_msgs/msg/Imu"
)

# ジャイロスコープストリーム
StreamConfig(
    ros_topic="/device_0/sensor_2/Gyro_0/imu/data",
    vrs_stream_id=1004,
    vrs_flavor="RealSense_D435i_Gyro",
    ros_msg_type="sensor_msgs/msg/Imu"
)
```

---

## 6. テスト戦略

### 6.1 単体テスト

- `test_imu_accel_stream_creation`: Accelストリーム作成テスト
- `test_imu_gyro_stream_creation`: Gyroストリーム作成テスト
- `test_imu_accel_configuration`: Accel Configurationレコード作成テスト
- `test_imu_gyro_configuration`: Gyro Configurationレコード作成テスト
- `test_imu_accel_data_conversion`: Accelデータ変換テスト（struct.pack検証）
- `test_imu_gyro_data_conversion`: Gyroデータ変換テスト（struct.pack検証）

### 6.2 統合テスト

- `test_imu_end_to_end`: d435i_walking.bag → VRS変換 → VRS Inspector確認
- IMUストリーム読み込みテスト
- タイムスタンプ同期テスト

### 6.3 検証項目

- [ ] VRSファイルにstream 1003, 1004が存在
- [ ] Configurationレコードが正しく書き込まれている
- [ ] Dataレコード数がROSbagと一致
- [ ] タイムスタンプが単調増加
- [ ] VRS Inspectorでsensor_type, unit, sample_rateが表示される
- [ ] バイナリデータが正しくパック/アンパックできる

---

## 7. 制約事項

### 7.1 RealSense D435i IMUの制約

- **Covariance情報なし:** ROSbag内のcovariance行列は全て0
- **IMU intrinsic未使用:** ImuIntrinsicメッセージも全て0
- **Orientation未使用:** Quaternion orientationは常に0
- **Frame ID:** 数値 `0`（文字列ではない）

### 7.2 VRS形式の制約

- **RecordFormat/DataLayout:** 現在の実装ではDataLayoutは固定（timestamp + custom binary）
- **Metadata:** sensor_typeやunitはConfigurationレコードに格納
- **共分散行列:** 将来的にConfigurationに追加可能（現状は0）

---

## 8. 参考資料

- [sensor_msgs/Imu定義](http://docs.ros.org/en/api/sensor_msgs/html/msg/Imu.html)
- [RealSense IMU仕様](https://www.intelrealsense.com/depth-camera-d435i/)
- [VRS Data Layout](https://facebookresearch.github.io/vrs/docs/DataLayout/)

---

**作成日:** 2025-11-19
**更新日:** 2025-11-19
**バージョン:** 1.0.0
