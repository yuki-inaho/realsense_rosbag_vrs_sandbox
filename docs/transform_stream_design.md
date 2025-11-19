# Transformストリーム設計仕様

**日付:** 2025-11-19
**バージョン:** 1.0.0
**対象:** RealSense D435i Transform データ（Camera Extrinsic Parameters）

---

## 1. 概要

本ドキュメントは、RealSense D435i Transform データ（カメラ外部パラメータ）をVRS形式に変換するためのストリーム設計仕様を定義します。

### 目的

- ROSbag形式のTransformデータ（geometry_msgs/msg/Transform）をVRS形式に変換
- カメラ間の空間的関係を保存（RGB-Depth間の相対位置・姿勢）
- ROSbagと同等の情報再生機能を提供（translation, rotation）
- Meta VRSエコシステムとの互換性確保

---

## 2. ROSbagデータ構造

### 2.1 ROSbagトピック

| トピック名 | メッセージ型 | 説明 | メッセージ数（実測） |
|-----------|------------|------|-------------------|
| `/device_0/sensor_0/Depth_0/tf/0` | geometry_msgs/msg/Transform | Depthカメラ外部パラメータ | 1（静的） |
| `/device_0/sensor_1/Color_0/tf/0` | geometry_msgs/msg/Transform | Colorカメラ外部パラメータ | 1（静的） |

### 2.2 geometry_msgs/msg/Transform メッセージ構造

```
geometry_msgs/Vector3 translation
  float64 x
  float64 y
  float64 z

geometry_msgs/Quaternion rotation
  float64 x
  float64 y
  float64 z
  float64 w
```

**注意:** geometry_msgs/Transformには`header`フィールドが存在しない（geometry_msgs/TransformStampedとは異なる）

### 2.3 実測データ例

**Depth Camera Transform (`/device_0/sensor_0/Depth_0/tf/0`):**
- Translation: `x=0.000000, y=0.000000, z=0.000000` (m)
- Rotation: `x=0.000000, y=0.000000, z=0.000000, w=1.000000` (quaternion)
- **解釈:** Identity transform（基準座標系）

**Color Camera Transform (`/device_0/sensor_1/Color_0/tf/0`):**
- Translation: `x=0.015014, y=0.000251, z=0.000425` (m)
- Rotation: `x=0.001509, y=0.001900, z=0.006073, w=0.999979` (quaternion)
- **解釈:** Depthカメラ基準での相対位置・姿勢（約15mm x方向オフセット）

### 2.4 データ特性

- **静的Transform:** 各トピック1メッセージのみ（ROSbag記録開始時に1回発行）
- **座標系:** RealSense D435i ハードウェア設計に基づく固定値
- **用途:** RGB-Depth間のキャリブレーション、Point Cloud生成、Sensor Fusion

---

## 3. VRSストリーム設計

### 3.1 ストリームID割り当て

| ストリームID | Flavor名 | 説明 | データソース |
|------------|---------|------|------------|
| 1001 | RealSense_D435i_Color | RGB画像 | /device_0/sensor_1/Color_0/image/data |
| 1002 | RealSense_D435i_Depth | Depth画像 | /device_0/sensor_0/Depth_0/image/data |
| 1003 | RealSense_D435i_Accel | 加速度計 | /device_0/sensor_2/Accel_0/imu/data |
| 1004 | RealSense_D435i_Gyro | ジャイロスコープ | /device_0/sensor_2/Gyro_0/imu/data |
| 1005 | RealSense_D435i_Depth_Extrinsic | Depthカメラ外部パラメータ | /device_0/sensor_0/Depth_0/tf/0 |
| 1006 | RealSense_D435i_Color_Extrinsic | Colorカメラ外部パラメータ | /device_0/sensor_1/Color_0/tf/0 |

### 3.2 Configuration レコード構造

Transformは静的データのため、**Configurationレコードのみ**に格納します（Dataレコードは不要）。

#### Stream 1005 (Depth Extrinsic)

```json
{
  "transform_type": "static",
  "sensor_name": "Depth",
  "reference_frame": "device_0",
  "translation": {
    "x": 0.0,
    "y": 0.0,
    "z": 0.0,
    "unit": "meters"
  },
  "rotation": {
    "x": 0.0,
    "y": 0.0,
    "z": 0.0,
    "w": 1.0,
    "format": "quaternion"
  }
}
```

#### Stream 1006 (Color Extrinsic)

```json
{
  "transform_type": "static",
  "sensor_name": "Color",
  "reference_frame": "device_0",
  "translation": {
    "x": 0.015014,
    "y": 0.000251,
    "z": 0.000425,
    "unit": "meters"
  },
  "rotation": {
    "x": 0.001509,
    "y": 0.001900,
    "z": 0.006073,
    "w": 0.999979,
    "format": "quaternion"
  }
}
```

### 3.3 Data レコード構造

静的Transformのため、**Dataレコードは作成しない**。

**理由:**
- Transformは時系列データではない（1回のみ発行される静的値）
- ConfigurationレコードにすべてのTransform情報を格納できる
- VRSファイルサイズの節約

---

## 4. タイムスタンプ変換

Transformは静的データのため、タイムスタンプ変換は不要です。

ROSbagではtimestamp=0.000で発行されますが、VRSではConfigurationレコードに格納するため、タイムスタンプは関係しません。

---

## 5. 実装方針

### 5.1 Phase 4C: Transform変換実装の流れ

1. **手順4C.1:** Transformストリーム設計（本ドキュメント）
2. **手順4C.2:** Transform Configurationレコード仕様策定
3. **手順4C.3:** RosbagToVRSConverter にTransform変換ロジック追加
4. **手順4C.4:** Transform変換テスト実行（d435i_walking.bag）
5. **手順4C.5:** コミット・プッシュ

### 5.2 RosbagToVRSConverter 実装メソッド

```python
def _cache_transforms(self, reader: Any) -> None:
    """
    Cache Transform messages for Configuration records

    Transform topics:
    - /device_0/sensor_0/Depth_0/tf/0 (Depth Extrinsic)
    - /device_0/sensor_1/Color_0/tf/0 (Color Extrinsic)
    """
    transform_topics = [
        "/device_0/sensor_0/Depth_0/tf/0",
        "/device_0/sensor_1/Color_0/tf/0"
    ]

    with reader:
        connections = [x for x in reader.connections if x.topic in transform_topics]

        for connection, timestamp, rawdata in reader.messages(connections=connections):
            msg = reader.deserialize(rawdata, connection.msgtype)

            # Cache by topic
            self._stats["transform_cache"][connection.topic] = msg

            if self.config.verbose:
                print(f"Cached Transform from {connection.topic}")

def _write_transform_depth_configuration(
    self,
    writer: VRSWriter,
    stream_config: StreamConfig,
    topic: str
) -> None:
    """Write Depth Extrinsic Configuration record"""
    transform_msg = self._stats["transform_cache"].get(topic)

    if transform_msg is None:
        # Default to identity transform if not found
        config_data = {
            "transform_type": "static",
            "sensor_name": "Depth",
            "reference_frame": "device_0",
            "translation": {"x": 0.0, "y": 0.0, "z": 0.0, "unit": "meters"},
            "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0, "format": "quaternion"}
        }
    else:
        config_data = {
            "transform_type": "static",
            "sensor_name": "Depth",
            "reference_frame": "device_0",
            "translation": {
                "x": transform_msg.translation.x,
                "y": transform_msg.translation.y,
                "z": transform_msg.translation.z,
                "unit": "meters"
            },
            "rotation": {
                "x": transform_msg.rotation.x,
                "y": transform_msg.rotation.y,
                "z": transform_msg.rotation.z,
                "w": transform_msg.rotation.w,
                "format": "quaternion"
            }
        }

    writer.write_configuration(stream_config.stream_id, config_data)

def _write_transform_color_configuration(
    self,
    writer: VRSWriter,
    stream_config: StreamConfig,
    topic: str
) -> None:
    """Write Color Extrinsic Configuration record"""
    transform_msg = self._stats["transform_cache"].get(topic)

    if transform_msg is None:
        raise ValueError(f"Transform message not found for topic: {topic}")

    config_data = {
        "transform_type": "static",
        "sensor_name": "Color",
        "reference_frame": "device_0",
        "translation": {
            "x": transform_msg.translation.x,
            "y": transform_msg.translation.y,
            "z": transform_msg.translation.z,
            "unit": "meters"
        },
        "rotation": {
            "x": transform_msg.rotation.x,
            "y": transform_msg.rotation.y,
            "z": transform_msg.rotation.z,
            "w": transform_msg.rotation.w,
            "format": "quaternion"
        }
    }

    writer.write_configuration(stream_config.stream_id, config_data)
```

### 5.3 StreamConfig 更新

```python
# Depth Extrinsic ストリーム
StreamConfig(
    ros_topic="/device_0/sensor_0/Depth_0/tf/0",
    vrs_stream_id=1005,
    vrs_flavor="RealSense_D435i_Depth_Extrinsic",
    ros_msg_type="geometry_msgs/msg/Transform",
    stream_type="transform_depth"
)

# Color Extrinsic ストリーム
StreamConfig(
    ros_topic="/device_0/sensor_1/Color_0/tf/0",
    vrs_stream_id=1006,
    vrs_flavor="RealSense_D435i_Color_Extrinsic",
    ros_msg_type="geometry_msgs/msg/Transform",
    stream_type="transform_color"
)
```

**注意:** Transformストリームは**Dataレコードを持たない**ため、_process_messagesでは処理しない。Configurationレコードのみを_write_configurationsで書き込む。

---

## 6. テスト戦略

### 6.1 単体テスト

- `test_transform_stream_creation`: Transform ストリーム作成テスト（stream 1005, 1006）
- `test_transform_depth_configuration`: Depth Extrinsic Configurationレコード作成テスト
- `test_transform_color_configuration`: Color Extrinsic Configurationレコード作成テスト
- `test_transform_cache`: Transform message キャッシュ機能テスト

### 6.2 統合テスト

- `test_transform_end_to_end`: d435i_walking.bag → VRS変換 → VRS Inspector確認
- Transformストリーム読み込みテスト
- Configurationレコード内容検証

### 6.3 検証項目

- [ ] VRSファイルにstream 1005, 1006が存在
- [ ] Configurationレコードが正しく書き込まれている（translation, rotation）
- [ ] Depth Extrinsicがidentity transformである
- [ ] Color Extrinsicが実測値と一致する
- [ ] VRS Inspectorでtransform_type, sensor_name, reference_frameが表示される
- [ ] Dataレコードが存在しない（Configurationのみ）

---

## 7. 制約事項

### 7.1 RealSense D435i Transformの制約

- **静的Transform:** 時系列データではない（1メッセージのみ）
- **header無し:** geometry_msgs/Transformにはheaderフィールドが存在しない
- **座標系:** device_0を基準座標系とする
- **キャリブレーション:** 工場出荷時キャリブレーション値（固定）

### 7.2 VRS形式の制約

- **Configurationのみ:** 静的データはConfigurationレコードに格納
- **Dataレコード不要:** 時系列データでないため省略
- **RecordFormat:** Configurationは自由形式JSON（VRSライブラリが対応）

---

## 8. 参考資料

- [geometry_msgs/Transform定義](http://docs.ros.org/en/api/geometry_msgs/html/msg/Transform.html)
- [RealSense D435i 仕様](https://www.intelrealsense.com/depth-camera-d435i/)
- [VRS Configuration Records](https://facebookresearch.github.io/vrs/docs/DataLayout/)

---

**作成日:** 2025-11-19
**更新日:** 2025-11-19
**バージョン:** 1.0.0
