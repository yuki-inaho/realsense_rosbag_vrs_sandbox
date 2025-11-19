# Optionsストリーム設計仕様

**日付:** 2025-11-19
**バージョン:** 1.0.0
**対象:** RealSense D435i Options データ（カメラ・センサー設定オプション）

---

## 1. 概要

本ドキュメントは、RealSense D435i Options データ（カメラ・センサー設定オプション）をVRS形式に変換するためのストリーム設計仕様を定義します。

### 目的

- ROSbag形式のOptionsデータ（std_msgs/msg/Float32, std_msgs/msg/String）をVRS形式に変換
- カメラ・センサーの全設定値を保存（Exposure, Gain, Laser Power等）
- ROSbagと同等の情報再生機能を提供（設定値 + 説明文）
- 完全な再現性を確保（同一設定での撮影再現が可能）

---

## 2. ROSbagデータ構造

### 2.1 ROSbagトピック

Options は各設定項目ごとに2つのトピックを持ちます：

| トピックパターン | メッセージ型 | 説明 | メッセージ数 |
|---------------|------------|------|-------------|
| `/device_0/sensor_*/option/*/value` | std_msgs/msg/Float32 | 設定値（数値） | 1（静的） |
| `/device_0/sensor_*/option/*/description` | std_msgs/msg/String | 設定の説明文 | 1（静的） |

**総計:** 60トピック（25オプション × 2トピック）

### 2.2 オプション一覧

d435i_walking.bag に含まれる25個のオプション：

| オプション名 | センサー | 実測値例 | 説明 |
|-----------|---------|---------|------|
| Exposure | sensor_1 (Color) | 156.0 | 露光時間制御 |
| Gain | sensor_1 (Color) | 64.0 | UVC画像ゲイン |
| Enable Auto Exposure | sensor_1 (Color) | 1.0 | 自動露出有効化 |
| Enable Auto White Balance | sensor_1 (Color) | 1.0 | 自動ホワイトバランス |
| White Balance | sensor_1 (Color) | 4600.0 | ホワイトバランス値 |
| Brightness | sensor_1 (Color) | 0.0 | 明るさ |
| Contrast | sensor_1 (Color) | 50.0 | コントラスト |
| Saturation | sensor_1 (Color) | 64.0 | 彩度 |
| Sharpness | sensor_1 (Color) | 50.0 | シャープネス |
| Gamma | sensor_1 (Color) | 300.0 | ガンマ値 |
| Hue | sensor_1 (Color) | 0.0 | 色相 |
| Backlight Compensation | sensor_1 (Color) | 0.0 | 逆光補正 |
| Power Line Frequency | sensor_1 (Color) | 3.0 | 電源周波数 |
| Auto Exposure Priority | sensor_1 (Color) | 0.0 | 自動露出優先度 |
| Visual Preset | sensor_0 (Depth) | 5.0 | 詳細モードプリセット |
| Laser Power | sensor_0 (Depth) | 150.0 | レーザー出力（mW） |
| Emitter Enabled | sensor_0 (Depth) | 1.0 | エミッター有効化 |
| Depth Units | sensor_0 (Depth) | 0.001 | Depthの単位（m） |
| Stereo Baseline | sensor_0 (Depth) | 50.0 | ステレオベースライン（mm） |
| Inter Cam Sync Mode | sensor_0 (Depth) | 0.0 | カメラ間同期モード |
| Output Trigger Enabled | sensor_0 (Depth) | 0.0 | 出力トリガー有効化 |
| Asic Temperature | sensor_0 (Depth) | 34.0 | ASIC温度（℃） |
| Projector Temperature | sensor_0 (Depth) | 28.0 | プロジェクター温度（℃） |
| Error Polling Enabled | sensor_0 (Depth) | 1.0 | エラーポーリング有効化 |
| Frames Queue Size | sensor_0 (Depth) | 16.0 | フレームキューサイズ |

### 2.3 メッセージ構造

#### std_msgs/msg/Float32 (value)

```
float32 data
```

#### std_msgs/msg/String (description)

```
string data
```

### 2.4 実測データ例

**Exposure (Color Camera):**
- Value: `156.0`
- Description: `"Controls exposure time of color camera. Setting any value will disable auto exposure."`

**Laser Power (Depth Camera):**
- Value: `150.0`
- Description: `"Manual laser power in mw. applicable only when laser power mode is set to Manual"`

**Depth Units (Depth Camera):**
- Value: `0.001`
- Description: `"Number of meters represented by a single depth unit"`

### 2.5 データ特性

- **静的Options:** 各トピック1メッセージのみ（ROSbag記録開始時に1回発行）
- **センサー別:** sensor_0 (Depth), sensor_1 (Color), sensor_2 (IMU)
- **用途:** カメラ設定の完全再現、撮影条件の記録
- **重要性:** 同一条件での撮影再現に必須

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
| 2001 | RealSense_D435i_Device_Info | デバイス情報 | /device_0/info |
| 2002 | RealSense_D435i_Sensor0_Info | Sensor0情報 (Stereo) | /device_0/sensor_0/info |
| 2003 | RealSense_D435i_Sensor1_Info | Sensor1情報 (RGB) | /device_0/sensor_1/info |
| 2004 | RealSense_D435i_Sensor2_Info | Sensor2情報 (Motion) | /device_0/sensor_2/info |
| **2005** | **RealSense_D435i_Options** | **全センサーのオプション設定** | **/device_0/sensor_*/option/\*/** |

**設計方針:**
- **単一ストリーム:** 全25オプションを1つのストリームに集約
- **理由:** オプションは関連する設定データ、Device Infoと同様のパターン
- **利点:** シンプルな管理、VRSファイルのストリーム数削減

### 3.2 Configuration レコード構造

Optionsは静的データのため、**Configurationレコードのみ**に格納します（Dataレコードは不要）。

#### Stream 2005 (Options)

```json
{
  "info_type": "options",
  "total_options": 25,
  "options": [
    {
      "name": "Exposure",
      "sensor": "sensor_1",
      "value": 156.0,
      "description": "Controls exposure time of color camera. Setting any value will disable auto exposure."
    },
    {
      "name": "Gain",
      "sensor": "sensor_1",
      "value": 64.0,
      "description": "UVC image gain"
    },
    {
      "name": "Enable Auto Exposure",
      "sensor": "sensor_1",
      "value": 1.0,
      "description": "Enable / disable auto-exposure"
    },
    {
      "name": "Visual Preset",
      "sensor": "sensor_0",
      "value": 5.0,
      "description": "Advanced-Mode Preset"
    },
    {
      "name": "Laser Power",
      "sensor": "sensor_0",
      "value": 150.0,
      "description": "Manual laser power in mw. applicable only when laser power mode is set to Manual"
    },
    {
      "name": "Depth Units",
      "sensor": "sensor_0",
      "value": 0.001,
      "description": "Number of meters represented by a single depth unit"
    }
  ]
}
```

**フィールド説明:**
- `info_type`: 固定値 `"options"`
- `total_options`: オプション総数（25）
- `options`: オプション配列
  - `name`: オプション名（スペース含む元の名前）
  - `sensor`: センサーID（`sensor_0`, `sensor_1`, `sensor_2`）
  - `value`: 設定値（float32）
  - `description`: 説明文（string）

### 3.3 Data レコード構造

静的Optionsのため、**Dataレコードは作成しない**。

**理由:**
- Optionsは時系列データではない（1回のみ発行される静的値）
- ConfigurationレコードにすべてのOptions情報を格納できる
- VRSファイルサイズの節約

---

## 4. タイムスタンプ変換

Optionsは静的データのため、タイムスタンプ変換は不要です。

ROSbagではtimestamp=0.000で発行されますが、VRSではConfigurationレコードに格納するため、タイムスタンプは関係しません。

---

## 5. 実装方針

### 5.1 Phase 4F: Options変換実装の流れ

1. **手順4F.1:** Optionsストリーム設計（本ドキュメント）
2. **手順4F.2:** Options Configurationレコード仕様策定
3. **手順4F.3:** RosbagToVRSConverter にOptions変換ロジック追加
4. **手順4F.4:** Options変換テスト実行（d435i_walking.bag）
5. **手順4F.5:** コミット・プッシュ

### 5.2 RosbagToVRSConverter 実装メソッド

```python
def _cache_options(self, reader: Any) -> None:
    """
    Cache Options messages for Configuration record

    Options topics:
    - /device_0/sensor_*/option/*/value (25 topics)
    - /device_0/sensor_*/option/*/description (25 topics)
    """
    options_dict = {}  # {option_name: {sensor, value, description}}

    with reader:
        # Find all option topics
        option_connections = [
            c for c in reader.connections
            if '/option/' in c.topic
        ]

        for connection, timestamp, rawdata in reader.messages(connections=option_connections):
            msg = reader.deserialize(rawdata, connection.msgtype)

            # Parse topic: /device_0/sensor_X/option/OPTION_NAME/TYPE
            parts = connection.topic.split('/')
            sensor_id = parts[2]  # sensor_0, sensor_1, sensor_2
            option_name = parts[4]  # Exposure, Gain, etc.
            option_type = parts[5]  # value or description

            # Initialize option entry if not exists
            if option_name not in options_dict:
                options_dict[option_name] = {
                    'sensor': sensor_id,
                    'value': None,
                    'description': None
                }

            # Store value or description
            if option_type == 'value':
                options_dict[option_name]['value'] = float(msg.data)
            elif option_type == 'description':
                options_dict[option_name]['description'] = str(msg.data)

        self._stats["options_cache"] = options_dict

        if self.config.verbose:
            print(f"Cached {len(options_dict)} Options")

def _write_options_configuration(
    self,
    writer: VRSWriter,
    stream_config: StreamConfig,
    topic: str
) -> None:
    """Write Options Configuration record"""
    options_dict = self._stats.get("options_cache", {})

    # Build options array
    options_array = []
    for name, data in sorted(options_dict.items()):
        options_array.append({
            "name": name,
            "sensor": data['sensor'],
            "value": data['value'],
            "description": data['description']
        })

    config_data = {
        "info_type": "options",
        "total_options": len(options_array),
        "options": options_array
    }

    writer.write_configuration(stream_config.stream_id, config_data)

    if self.config.verbose:
        print(f"Wrote Configuration for stream {stream_config.stream_id} (Options): {len(options_array)} options")
```

### 5.3 StreamConfig 更新

```python
# Options ストリーム (RGBD_IMU_STREAMS に追加)
"/device_0/sensor_0/option": StreamConfig(
    stream_id=2005,
    stream_type="options",
    recordable_type_id="ForwardCamera",
    flavor="RealSense_D435i_Options|id:2005"
)
```

**注意:**
- Optionsストリームは**Dataレコードを持たない**ため、`_process_messages`では処理しない
- Configurationレコードのみを`_write_configurations`で書き込む
- トピックマッピングは代表トピック `/device_0/sensor_0/option` を使用（実際は `_cache_options` で全optionsトピックを処理）

---

## 6. テスト戦略

### 6.1 単体テスト

- `test_options_stream_creation`: Options ストリーム作成テスト（stream 2005）
- `test_options_configuration`: Options Configurationレコード作成テスト
- `test_options_cache`: Options message キャッシュ機能テスト（25オプション）
- `test_options_parsing`: トピック名パース機能テスト（sensor_id, option_name抽出）

### 6.2 統合テスト

- `test_options_end_to_end`: d435i_walking.bag → VRS変換 → VRS Inspector確認
- Optionsストリーム読み込みテスト
- Configurationレコード内容検証（25オプション全て含まれているか）

### 6.3 検証項目

- [ ] VRSファイルにstream 2005が存在
- [ ] Configurationレコードが正しく書き込まれている（25オプション）
- [ ] 各オプションにname, sensor, value, descriptionが全て含まれる
- [ ] センサーID（sensor_0, sensor_1）が正しく抽出されている
- [ ] Value値がFloat32として正しく変換されている
- [ ] Description文字列が完全に保存されている
- [ ] VRS Inspectorでinfo_type, total_options, optionsが表示される
- [ ] Dataレコードが存在しない（Configurationのみ）

---

## 7. 制約事項

### 7.1 RealSense D435i Optionsの制約

- **静的Options:** 時系列データではない（1メッセージのみ）
- **センサー別:** sensor_0 (Depth), sensor_1 (Color) が主
- **値の型:** Float32のみ（整数値も浮動小数点として格納）
- **説明文:** 英語のみ、RealSense SDKが生成

### 7.2 VRS形式の制約

- **Configurationのみ:** 静的データはConfigurationレコードに格納
- **Dataレコード不要:** 時系列データでないため省略
- **RecordFormat:** Configurationは自由形式JSON（VRSライブラリが対応）

### 7.3 実装上の考慮事項

- **トピック名パース:** `/device_0/sensor_X/option/OPTION_NAME/TYPE` の構造に依存
- **オプション数:** 現在25個だが、将来的に増減する可能性あり
- **欠損データ:** value/descriptionのどちらかが欠けている場合の処理

---

## 8. 参考資料

- [std_msgs/Float32定義](http://docs.ros.org/en/api/std_msgs/html/msg/Float32.html)
- [std_msgs/String定義](http://docs.ros.org/en/api/std_msgs/html/msg/String.html)
- [RealSense D435i Options](https://dev.intelrealsense.com/docs/rs-options)
- [VRS Configuration Records](https://facebookresearch.github.io/vrs/docs/DataLayout/)

---

**作成日:** 2025-11-19
**更新日:** 2025-11-19
**バージョン:** 1.0.0
