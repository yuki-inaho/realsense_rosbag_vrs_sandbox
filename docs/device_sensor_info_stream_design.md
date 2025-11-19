# Device/Sensor Info ストリーム設計仕様

**日付:** 2025-11-19
**バージョン:** 1.0.0
**対象:** RealSense D435i Device/Sensor 情報データ

---

## 1. 概要

本ドキュメントは、RealSense D435i Device/Sensor情報（デバイスメタデータ、センサー名、ストリーム設定）をVRS形式に変換するための設計仕様を定義します。

### 目的

- ROSbag形式のDevice/Sensor情報をVRS形式に変換
- デバイス識別情報（シリアル番号、ファームウェアバージョン等）の保存
- センサー名称の保存
- ストリーム設定情報（encoding, fps）の既存Configurationへの追加
- ROSbagと同等の情報再生機能を提供

---

## 2. ROSbagデータ構造

### 2.1 ROSbagトピック

#### Device Info

| トピック名 | メッセージ型 | 説明 | メッセージ数 |
|-----------|------------|------|------------|
| `/device_0/info` | diagnostic_msgs/msg/KeyValue | デバイス情報（複数KeyValueペア） | 9 |

**KeyValueペア内容:**
```
Name: Intel RealSense D435I
Serial Number: 837212070292
Firmware Version: 05.10.13.00
255.255.255.255 (IP address?)
Recommended Firmware Version: 05.10.03.00
Physical Port: \\?\usb#vid_8086&pid_0b3a&mi_00#...
Debug Op Code: 15
Advanced Mode: YES
Product Id: 0B3A
Usb Type Descriptor: 3.2
```

#### Sensor Info

| トピック名 | メッセージ型 | 説明 | メッセージ数 |
|-----------|------------|------|------------|
| `/device_0/sensor_0/info` | diagnostic_msgs/msg/KeyValue | Stereo Module名称 | 1 |
| `/device_0/sensor_1/info` | diagnostic_msgs/msg/KeyValue | RGB Camera名称 | 1 |
| `/device_0/sensor_2/info` | diagnostic_msgs/msg/KeyValue | Motion Module名称 | 1 |

**内容:**
- sensor_0: Name=Stereo Module
- sensor_1: Name=RGB Camera
- sensor_2: Name=Motion Module

#### Stream Info

| トピック名 | メッセージ型 | 説明 | メッセージ数 |
|-----------|------------|------|------------|
| `/device_0/sensor_0/Depth_0/info` | realsense_msgs/msg/StreamInfo | Depthストリーム設定 | 1 |
| `/device_0/sensor_1/Color_0/info` | realsense_msgs/msg/StreamInfo | Colorストリーム設定 | 1 |
| `/device_0/sensor_2/Accel_0/info` | realsense_msgs/msg/StreamInfo | Accelストリーム設定 | 1 |
| `/device_0/sensor_2/Gyro_0/info` | realsense_msgs/msg/StreamInfo | Gyroストリーム設定 | 1 |

**StreamInfo メッセージ構造:**
```
string encoding        # 例: "rgb8", "mono16", "MOTION_XYZ32F"
uint32 fps             # 例: 30, 63, 200
bool is_recommended    # 推奨設定フラグ
```

**実測値:**
- Depth: encoding=mono16, fps=30, is_recommended=False
- Color: encoding=rgb8, fps=30, is_recommended=False
- Accel: encoding=MOTION_XYZ32F, fps=63, is_recommended=False
- Gyro: encoding=MOTION_XYZ32F, fps=200, is_recommended=False

### 2.2 データ特性

- **静的データ:** すべて時系列データではない（ROSbag記録開始時に1回発行）
- **デバイス固有情報:** シリアル番号等はハードウェア固有
- **メタデータ:** データ再生時の参照情報

---

## 3. VRSストリーム設計

### 3.1 設計方針

#### 3.1.1 Stream Info (encoding, fps) の扱い

Stream Info（encoding, fps, is_recommended）は**既存ストリームのConfigurationに追加**します。

- Stream 1001 (Color): Configurationに `fps`, `is_recommended` を追加（encodingは既存）
- Stream 1002 (Depth): Configurationに `fps`, `is_recommended` を追加（encodingは既存）
- Stream 1003 (Accel): Configurationに `fps`, `encoding`, `is_recommended` を追加
- Stream 1004 (Gyro): Configurationに `fps`, `encoding`, `is_recommended` を追加

#### 3.1.2 Device Info / Sensor Info の扱い

Device InfoとSensor Infoは**独立したストリーム**として作成します。
これにより、デバイス情報をVRSファイルから直接参照可能になります。

- Stream 2001: Device Info
- Stream 2002: Sensor Info - Stereo Module
- Stream 2003: Sensor Info - RGB Camera
- Stream 2004: Sensor Info - Motion Module

### 3.2 ストリームID割り当て

| ストリームID | Flavor名 | 説明 | データソース |
|------------|---------|------|------------|
| 1001 | RealSense_D435i_Color | RGB画像（fps追加） | /device_0/sensor_1/Color_0/image/data + info |
| 1002 | RealSense_D435i_Depth | Depth画像（fps追加） | /device_0/sensor_0/Depth_0/image/data + info |
| 1003 | RealSense_D435i_Accel | 加速度計（fps追加） | /device_0/sensor_2/Accel_0/imu/data + info |
| 1004 | RealSense_D435i_Gyro | ジャイロ（fps追加） | /device_0/sensor_2/Gyro_0/imu/data + info |
| 1005 | RealSense_D435i_Depth_Extrinsic | Depth外部パラメータ | /device_0/sensor_0/Depth_0/tf/0 |
| 1006 | RealSense_D435i_Color_Extrinsic | Color外部パラメータ | /device_0/sensor_1/Color_0/tf/0 |
| 2001 | RealSense_D435i_Device_Info | デバイス情報 | /device_0/info |
| 2002 | RealSense_D435i_Sensor0_Info | Stereo Module情報 | /device_0/sensor_0/info |
| 2003 | RealSense_D435i_Sensor1_Info | RGB Camera情報 | /device_0/sensor_1/info |
| 2004 | RealSense_D435i_Sensor2_Info | Motion Module情報 | /device_0/sensor_2/info |

### 3.3 Configuration レコード構造（更新版）

#### Stream 1001 (Color) - 更新

```json
{
  "width": 640,
  "height": 480,
  "encoding": "rgb8",
  "fps": 30,
  "is_recommended": false,
  "camera_k": [616.52, 0, 327.55, 0, 615.10, 238.23, 0, 0, 1],
  "camera_d": [0, 0, 0, 0, 0],
  "distortion_model": "Brown Conrady",
  "frame_id": ""
}
```

#### Stream 1002 (Depth) - 更新

```json
{
  "width": 1280,
  "height": 720,
  "encoding": "16UC1",
  "fps": 30,
  "is_recommended": false,
  "camera_k": [637.87, 0, 637.46, 0, 637.87, 361.98, 0, 0, 1],
  "camera_d": [0, 0, 0, 0, 0],
  "distortion_model": "Brown Conrady",
  "depth_scale": 0.001,
  "frame_id": ""
}
```

#### Stream 1003 (Accel) - 更新

```json
{
  "sensor_type": "accelerometer",
  "frame_id": "0",
  "unit": "m/s^2",
  "sample_rate": 44.0,
  "fps": 63,
  "encoding": "MOTION_XYZ32F",
  "is_recommended": false,
  "axes": ["x", "y", "z"],
  "range": null,
  "noise_variances": [0.0, 0.0, 0.0],
  "bias_variances": [0.0, 0.0, 0.0]
}
```

#### Stream 1004 (Gyro) - 更新

```json
{
  "sensor_type": "gyroscope",
  "frame_id": "0",
  "unit": "rad/s",
  "sample_rate": 55.0,
  "fps": 200,
  "encoding": "MOTION_XYZ32F",
  "is_recommended": false,
  "axes": ["x", "y", "z"],
  "range": null,
  "noise_variances": [0.0, 0.0, 0.0],
  "bias_variances": [0.0, 0.0, 0.0]
}
```

#### Stream 2001 (Device Info) - 新規

```json
{
  "info_type": "device",
  "device_name": "Intel RealSense D435I",
  "serial_number": "837212070292",
  "firmware_version": "05.10.13.00",
  "recommended_firmware_version": "05.10.03.00",
  "physical_port": "\\\\?\\usb#vid_8086&pid_0b3a&mi_00#...",
  "debug_op_code": "15",
  "advanced_mode": "YES",
  "product_id": "0B3A",
  "usb_type_descriptor": "3.2"
}
```

#### Stream 2002 (Sensor0 Info) - 新規

```json
{
  "info_type": "sensor",
  "sensor_id": "sensor_0",
  "sensor_name": "Stereo Module",
  "associated_streams": [1002, 1005]
}
```

#### Stream 2003 (Sensor1 Info) - 新規

```json
{
  "info_type": "sensor",
  "sensor_id": "sensor_1",
  "sensor_name": "RGB Camera",
  "associated_streams": [1001, 1006]
}
```

#### Stream 2004 (Sensor2 Info) - 新規

```json
{
  "info_type": "sensor",
  "sensor_id": "sensor_2",
  "sensor_name": "Motion Module",
  "associated_streams": [1003, 1004]
}
```

### 3.4 Data レコード構造

静的データのため、**Dataレコードは作成しない**（Configurationのみ）。

---

## 4. 実装方針

### 4.1 Phase 4D: Device/Sensor Info実装の流れ

1. **手順4D.1:** Device/Sensor Infoストリーム設計（本ドキュメント）
2. **手順4D.2:** Info Configuration/Dataレコード仕様策定
3. **手順4D.3:** RosbagToVRSConverter にInfo変換ロジック追加
4. **手順4D.4:** Info変換テスト実行（d435i_walking.bag）
5. **手順4D.5:** コミット・プッシュ

### 4.2 実装優先度

#### 高優先度（Phase 4D）:
1. 既存ストリーム（1001-1004）のConfigurationに fps, encoding, is_recommended を追加
2. Device Info ストリーム（2001）追加
3. Sensor Info ストリーム（2002-2004）追加

#### 低優先度（将来拡張）:
- hardware_reset トピックの対応（現状では不要と判断）

### 4.3 RosbagToVRSConverter 実装メソッド

```python
def _cache_stream_info(self, reader: Any) -> None:
    """
    Cache StreamInfo messages for Configuration records (Phase 4D)

    StreamInfo topics:
    - /device_0/sensor_0/Depth_0/info
    - /device_0/sensor_1/Color_0/info
    - /device_0/sensor_2/Accel_0/info
    - /device_0/sensor_2/Gyro_0/info
    """
    stream_info_topics = [
        "/device_0/sensor_0/Depth_0/info",
        "/device_0/sensor_1/Color_0/info",
        "/device_0/sensor_2/Accel_0/info",
        "/device_0/sensor_2/Gyro_0/info"
    ]

    with reader:
        connections = [x for x in reader.connections if x.topic in stream_info_topics]

        if not connections:
            if self.config.verbose:
                print("No StreamInfo topics found in ROSbag (skipping)")
            return

        for connection, timestamp, rawdata in reader.messages(connections=connections):
            msg = reader.deserialize(rawdata, connection.msgtype)
            self._stats["stream_info_cache"][connection.topic] = msg

            if self.config.verbose:
                print(f"Cached StreamInfo from {connection.topic}")

def _cache_device_info(self, reader: Any) -> None:
    """
    Cache Device Info messages (Phase 4D)

    Device Info topics:
    - /device_0/info (multiple KeyValue pairs)
    """
    device_info_topic = "/device_0/info"

    device_info_dict = {}

    with reader:
        connections = [x for x in reader.connections if x.topic == device_info_topic]

        if not connections:
            if self.config.verbose:
                print("No Device Info topics found in ROSbag (skipping)")
            return

        for connection, timestamp, rawdata in reader.messages(connections=connections):
            msg = reader.deserialize(rawdata, connection.msgtype)
            device_info_dict[msg.key] = msg.value

        self._stats["device_info_cache"] = device_info_dict

        if self.config.verbose:
            print(f"Cached Device Info ({len(device_info_dict)} key-value pairs)")

def _cache_sensor_info(self, reader: Any) -> None:
    """
    Cache Sensor Info messages (Phase 4D)

    Sensor Info topics:
    - /device_0/sensor_0/info
    - /device_0/sensor_1/info
    - /device_0/sensor_2/info
    """
    sensor_info_topics = [
        "/device_0/sensor_0/info",
        "/device_0/sensor_1/info",
        "/device_0/sensor_2/info"
    ]

    with reader:
        connections = [x for x in reader.connections if x.topic in sensor_info_topics]

        if not connections:
            if self.config.verbose:
                print("No Sensor Info topics found in ROSbag (skipping)")
            return

        for connection, timestamp, rawdata in reader.messages(connections=connections):
            msg = reader.deserialize(rawdata, connection.msgtype)
            self._stats["sensor_info_cache"][connection.topic] = msg

            if self.config.verbose:
                print(f"Cached Sensor Info from {connection.topic}")

# Update existing Configuration methods to include fps/encoding/is_recommended
def _write_color_configuration(self, writer: VRSWriter, stream_config: StreamConfig, topic: str) -> None:
    # ... existing code ...

    # Add StreamInfo if available
    stream_info_topic = "/device_0/sensor_1/Color_0/info"
    stream_info = self._stats.get("stream_info_cache", {}).get(stream_info_topic)

    if stream_info:
        config_data["fps"] = int(stream_info.fps)
        config_data["is_recommended"] = bool(stream_info.is_recommended)
```

### 4.4 StreamConfig 更新

```python
# Device Info ストリーム
StreamConfig(
    ros_topic="/device_0/info",
    vrs_stream_id=2001,
    vrs_flavor="RealSense_D435i_Device_Info",
    ros_msg_type="diagnostic_msgs/msg/KeyValue",
    stream_type="device_info"
)

# Sensor Info ストリーム (sensor_0)
StreamConfig(
    ros_topic="/device_0/sensor_0/info",
    vrs_stream_id=2002,
    vrs_flavor="RealSense_D435i_Sensor0_Info",
    ros_msg_type="diagnostic_msgs/msg/KeyValue",
    stream_type="sensor_info"
)

# Sensor Info ストリーム (sensor_1)
StreamConfig(
    ros_topic="/device_0/sensor_1/info",
    vrs_stream_id=2003,
    vrs_flavor="RealSense_D435i_Sensor1_Info",
    ros_msg_type="diagnostic_msgs/msg/KeyValue",
    stream_type="sensor_info"
)

# Sensor Info ストリーム (sensor_2)
StreamConfig(
    ros_topic="/device_0/sensor_2/info",
    vrs_stream_id=2004,
    vrs_flavor="RealSense_D435i_Sensor2_Info",
    ros_msg_type="diagnostic_msgs/msg/KeyValue",
    stream_type="sensor_info"
)
```

---

## 5. テスト戦略

### 5.1 単体テスト

- `test_stream_info_cache`: StreamInfo キャッシュ機能テスト
- `test_device_info_cache`: Device Info キャッシュ機能テスト（9つのKeyValueペア）
- `test_sensor_info_cache`: Sensor Info キャッシュ機能テスト（3センサー）
- `test_color_configuration_with_fps`: Color Configuration に fps/is_recommended 追加テスト
- `test_device_info_stream_creation`: Device Info ストリーム作成テスト（stream 2001）
- `test_sensor_info_stream_creation`: Sensor Info ストリーム作成テスト（stream 2002-2004）

### 5.2 統合テスト

- `test_device_sensor_info_end_to_end`: d435i_walking.bag → VRS変換 → VRS Inspector確認
- Device/Sensor Infoストリーム読み込みテスト
- Configuration内容検証

### 5.3 検証項目

- [ ] VRSファイルにstream 2001-2004が存在
- [ ] Stream 1001-1004のConfigurationに fps, is_recommended が追加されている
- [ ] Device Info (2001) に9つのKeyValueペアが格納されている
- [ ] Sensor Info (2002-2004) にセンサー名が格納されている
- [ ] VRS Inspectorでinfo_type, device_name, sensor_nameが表示される
- [ ] Dataレコードが存在しない（Configurationのみ）

---

## 6. 制約事項

### 6.1 RealSense D435i Info の制約

- **静的データ:** 時系列データではない（1メッセージのみ）
- **KeyValue形式:** Device Infoは複数メッセージで構成（9つ）
- **単一値:** Sensor Infoは各センサー1メッセージのみ

### 6.2 VRS形式の制約

- **Configurationのみ:** 静的データはConfigurationレコードに格納
- **Dataレコード不要:** 時系列データでないため省略

---

## 7. 参考資料

- [diagnostic_msgs/KeyValue定義](http://docs.ros.org/en/api/diagnostic_msgs/html/msg/KeyValue.html)
- [realsense_msgs/StreamInfo](https://github.com/IntelRealSense/realsense-ros)
- [RealSense D435i 仕様](https://www.intelrealsense.com/depth-camera-d435i/)
- [VRS Configuration Records](https://facebookresearch.github.io/vrs/docs/DataLayout/)

---

**作成日:** 2025-11-19
**更新日:** 2025-11-19
**バージョン:** 1.0.0
