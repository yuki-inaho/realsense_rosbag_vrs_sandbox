# ROSbag → VRS マッピング設計書

**作成日**: 2025年11月19日
**対象**: RealSense D435i ROSbag → VRS変換
**参照**: `docs/rosbag_20251119_112125_structure.md`

---

## 1. ストリーム定義

### Stream 1001: Color Image

- **Source ROSbagトピック**: `/device_0/sensor_1/Color_0/image/data`
- **Message Type**: `sensor_msgs/msg/Image`
- **VRS RecordableTypeId**: `RecordableTypeId::ForwardCamera` (前方カメラ)
- **Stream Flavor**: `"RealSense_D435i_Color|id:1001"`

#### Configuration Record (DataLayout)

- **width**: `DataPieceValue<uint32_t>` - 画像幅（1920）
- **height**: `DataPieceValue<uint32_t>` - 画像高さ（1080）
- **encoding**: `DataPieceString` - ピクセルエンコーディング（"rgb8" or "bgr8"）
- **camera_k**: `DataPieceVector<double>` - カメラ内部パラメータK行列（9要素）
- **camera_d**: `DataPieceVector<double>` - 歪み係数D（5要素）
- **distortion_model**: `DataPieceString` - 歪みモデル（"plumb_bob"）

#### Data Record (DataLayout + Image Block)

- **DataLayout部分**:
  - **timestamp**: `DataPieceValue<double>` - タイムスタンプ（秒）
  - **frame_id**: `DataPieceString` - フレームID（ROS座標系識別子）

- **Image Block部分**:
  - **ImageFormat**: `ImageFormat::RAW`
  - **PixelFormat**: `PixelFormat::RGB8` or `PixelFormat::BGR8`
  - **Image Size**: width × height × 3 bytes

---

### Stream 1002: Depth Image

- **Source ROSbagトピック**: `/device_0/sensor_0/Depth_0/image/data`
- **Message Type**: `sensor_msgs/msg/Image`
- **VRS RecordableTypeId**: `RecordableTypeId::ForwardCamera` (深度センサーとして)
- **Stream Flavor**: `"RealSense_D435i_Depth|id:1002"`

#### Configuration Record (DataLayout)

- **width**: `DataPieceValue<uint32_t>` - 画像幅（1280）
- **height**: `DataPieceValue<uint32_t>` - 画像高さ（720）
- **encoding**: `DataPieceString` - ピクセルエンコーディング（"16UC1"）
- **camera_k**: `DataPieceVector<double>` - カメラ内部パラメータK行列（9要素）
- **camera_d**: `DataPieceVector<double>` - 歪み係数D（5要素）
- **distortion_model**: `DataPieceString` - 歪みモデル（"plumb_bob"）
- **depth_scale**: `DataPieceValue<float>` - 深度スケール（mm→meters変換係数、通常0.001）

#### Data Record (DataLayout + Image Block)

- **DataLayout部分**:
  - **timestamp**: `DataPieceValue<double>` - タイムスタンプ（秒）
  - **frame_id**: `DataPieceString` - フレームID

- **Image Block部分**:
  - **ImageFormat**: `ImageFormat::RAW`
  - **PixelFormat**: `PixelFormat::GREY16` (16-bit unsigned integer)
  - **Image Size**: width × height × 2 bytes

---

### Stream 2001: IMU Accelerometer

- **Source ROSbagトピック**: `/device_0/sensor_2/Accel_0/imu/data`
- **Message Type**: `sensor_msgs/msg/Imu`
- **VRS RecordableTypeId**: `RecordableTypeId::MotionSensor` (IMUセンサー)
- **Stream Flavor**: `"RealSense_D435i_IMU_Accel|id:2001"`

#### Configuration Record (DataLayout)

- **sensor_type**: `DataPieceString` - "accelerometer"
- **sampling_rate**: `DataPieceValue<float>` - サンプリングレート（Hz、例: 63, 250）
- **range**: `DataPieceValue<float>` - 測定範囲（m/s²、例: ±4g = 39.2 m/s²）
- **resolution**: `DataPieceValue<float>` - 分解能（m/s²）

#### Data Record (DataLayout)

- **timestamp**: `DataPieceValue<double>` - タイムスタンプ（秒）
- **linear_acceleration**: `DataPieceValue<Point3Dd>` - 加速度ベクトル（x, y, z）[m/s²]
- **frame_id**: `DataPieceString` - フレームID

---

### Stream 2002: IMU Gyroscope

- **Source ROSbagトピック**: `/device_0/sensor_2/Gyro_0/imu/data`
- **Message Type**: `sensor_msgs/msg/Imu`
- **VRS RecordableTypeId**: `RecordableTypeId::MotionSensor` (IMUセンサー)
- **Stream Flavor**: `"RealSense_D435i_IMU_Gyro|id:2002"`

#### Configuration Record (DataLayout)

- **sensor_type**: `DataPieceString` - "gyroscope"
- **sampling_rate**: `DataPieceValue<float>` - サンプリングレート（Hz、例: 200, 400）
- **range**: `DataPieceValue<float>` - 測定範囲（rad/s、例: ±2000°/s ≈ 34.9 rad/s）
- **resolution**: `DataPieceValue<float>` - 分解能（rad/s）

#### Data Record (DataLayout)

- **timestamp**: `DataPieceValue<double>` - タイムスタンプ（秒）
- **angular_velocity**: `DataPieceValue<Point3Dd>` - 角速度ベクトル（x, y, z）[rad/s]
- **frame_id**: `DataPieceString` - フレームID

---

## 2. DataLayout C++実装例

### ColorImageConfigLayout

```cpp
class ColorImageConfigLayout : public vrs::AutoDataLayout {
public:
  vrs::DataPieceValue<uint32_t> width{"width"};
  vrs::DataPieceValue<uint32_t> height{"height"};
  vrs::DataPieceString encoding{"encoding"};
  vrs::DataPieceVector<double> camera_k{"camera_k"};
  vrs::DataPieceVector<double> camera_d{"camera_d"};
  vrs::DataPieceString distortion_model{"distortion_model"};
  vrs::AutoDataLayoutEnd endLayout;
};
```

### ColorImageDataLayout

```cpp
class ColorImageDataLayout : public vrs::AutoDataLayout {
public:
  vrs::DataPieceValue<double> timestamp{"timestamp"};
  vrs::DataPieceString frame_id{"frame_id"};
  vrs::AutoDataLayoutEnd endLayout;
};
```

### DepthImageConfigLayout

```cpp
class DepthImageConfigLayout : public vrs::AutoDataLayout {
public:
  vrs::DataPieceValue<uint32_t> width{"width"};
  vrs::DataPieceValue<uint32_t> height{"height"};
  vrs::DataPieceString encoding{"encoding"};
  vrs::DataPieceVector<double> camera_k{"camera_k"};
  vrs::DataPieceVector<double> camera_d{"camera_d"};
  vrs::DataPieceString distortion_model{"distortion_model"};
  vrs::DataPieceValue<float> depth_scale{"depth_scale"};
  vrs::AutoDataLayoutEnd endLayout;
};
```

### DepthImageDataLayout

```cpp
class DepthImageDataLayout : public vrs::AutoDataLayout {
public:
  vrs::DataPieceValue<double> timestamp{"timestamp"};
  vrs::DataPieceString frame_id{"frame_id"};
  vrs::AutoDataLayoutEnd endLayout;
};
```

### IMUConfigLayout

```cpp
class IMUConfigLayout : public vrs::AutoDataLayout {
public:
  vrs::DataPieceString sensor_type{"sensor_type"};  // "accelerometer" or "gyroscope"
  vrs::DataPieceValue<float> sampling_rate{"sampling_rate"};
  vrs::DataPieceValue<float> range{"range"};
  vrs::DataPieceValue<float> resolution{"resolution"};
  vrs::AutoDataLayoutEnd endLayout;
};
```

### IMU_AccelDataLayout

```cpp
class IMU_AccelDataLayout : public vrs::AutoDataLayout {
public:
  vrs::DataPieceValue<double> timestamp{"timestamp"};
  vrs::DataPieceValue<vrs::Point3Dd> linear_acceleration{"linear_acceleration"};
  vrs::DataPieceString frame_id{"frame_id"};
  vrs::AutoDataLayoutEnd endLayout;
};
```

### IMU_GyroDataLayout

```cpp
class IMU_GyroDataLayout : public vrs::AutoDataLayout {
public:
  vrs::DataPieceValue<double> timestamp{"timestamp"};
  vrs::DataPieceValue<vrs::Point3Dd> angular_velocity{"angular_velocity"};
  vrs::DataPieceString frame_id{"frame_id"};
  vrs::AutoDataLayoutEnd endLayout;
};
```

---

## 3. 実装優先順位

### 必須 (Phase 4A)

- **Stream 1001**: Color Image (Configuration + Data)
- **Stream 1002**: Depth Image (Configuration + Data)

**理由**: RGB-Dペアは最も重要なデータ。ほとんどのアプリケーションで必須。

### 推奨 (Phase 4B)

- **Stream 2001**: IMU Accelerometer
- **Stream 2002**: IMU Gyroscope

**理由**: IMUデータは6DOF tracking、SLAM等で重要。

### オプション (Phase 4C)

- **TF (Transform) 情報**: カメラ間・IMU間の座標変換行列
- **メタデータ**: ROSbag header情報（bagファイル作成時刻、記録デバイス情報等）
- **診断情報**: ROS diagnosticsトピック（センサー温度、エラー状態等）

---

## 4. 画像フォーマットマッピング

| ROS encoding | VRS ImageFormat | VRS PixelFormat | Bytes/Pixel | 備考 |
|--------------|-----------------|-----------------|-------------|------|
| `rgb8`       | `RAW`           | `RGB8`          | 3           | RGB順、8-bit/channel |
| `bgr8`       | `RAW`           | `BGR8`          | 3           | BGR順、8-bit/channel |
| `rgba8`      | `RAW`           | `RGBA8`         | 4           | RGBA順、8-bit/channel |
| `mono8`      | `RAW`           | `GREY8`         | 1           | グレースケール、8-bit |
| `16UC1`      | `RAW`           | `GREY16`        | 2           | グレースケール、16-bit unsigned（深度画像） |
| `32FC1`      | `RAW`           | `DEPTH32F`      | 4           | 32-bit float（深度画像、alternative） |

---

## 5. RecordFormatとImageBlockの統合

### Recordable実装パターン

```cpp
class ColorCameraRecordable : public vrs::Recordable {
  static const uint32_t kConfigVersion = 1;
  static const uint32_t kDataVersion = 1;

public:
  ColorCameraRecordable()
    : vrs::Recordable(vrs::RecordableTypeId::ForwardCamera, "RealSense_D435i_Color|id:1001") {

    // Configuration Record Format登録
    addRecordFormat(
        vrs::Record::Type::CONFIGURATION,
        kConfigVersion,
        configLayout_.getContentBlock(),
        {&configLayout_});

    // Data Record Format登録（DataLayout + ImageBlock）
    addRecordFormat(
        vrs::Record::Type::DATA,
        kDataVersion,
        dataLayout_.getContentBlock() + vrs::ContentBlock(vrs::ImageFormat::RAW),
        {&dataLayout_});
  }

  const vrs::Record* createConfigurationRecord() override {
    // カメラ内部パラメータを設定
    configLayout_.width.set(1920);
    configLayout_.height.set(1080);
    configLayout_.encoding.set("rgb8");
    configLayout_.camera_k.stage({fx, 0, cx, 0, fy, cy, 0, 0, 1});
    configLayout_.camera_d.stage({k1, k2, t1, t2, k3});
    configLayout_.distortion_model.set("plumb_bob");

    return createRecord(
        timestamp,
        vrs::Record::Type::CONFIGURATION,
        kConfigVersion,
        vrs::DataSource(configLayout_));
  }

  void addDataRecord(double timestamp, const std::string& frame_id, const std::vector<uint8_t>& pixels) {
    // メタデータを設定
    dataLayout_.timestamp.set(timestamp);
    dataLayout_.frame_id.set(frame_id);

    // DataSource: DataLayout + Image pixels
    createRecord(
        timestamp,
        vrs::Record::Type::DATA,
        kDataVersion,
        vrs::DataSource(dataLayout_, {pixels.data(), pixels.size()}));
  }

private:
  ColorImageConfigLayout configLayout_;
  ColorImageDataLayout dataLayout_;
};
```

---

## 6. 既知の問題と制約

### PyVRS互換性問題

- **問題**: pytest実行時にPyVRSがクラッシュ（`currentLayout_ != nullptr` failed）
- **回避策**: C++ VRSReader実装を優先使用
- **影響**: Pythonでの読み取りは手動スクリプトのみ対応

### ImageブロックのDataLayout統合

- **検討事項**: ImageブロックとDataLayoutの組み合わせ方
- **推奨方式**: DataLayout (metadata) + ImageBlock (pixel data)
- **参考**: `third/vrs/sample_code/SampleRecordFormatDataLayout.cpp` の実装

### タイムスタンプの扱い

- **ROSbag**: 各メッセージに header.stamp (ros::Time)
- **VRS**: 各レコードにdouble型タイムスタンプ（秒単位）
- **変換**: `timestamp_sec = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9`

### 座標系の違い

- **ROSbag**: 各センサーごとに異なるframe_id (coordinate frame)
- **VRS**: ストリームごとに独立（外部パラメータは別途保存が必要）
- **推奨**: TF情報を別ストリームまたはConfiguration Recordに保存

---

## 7. 次のステップ

### Phase 4実装に向けて

1. **C++実装**: `pyvrs_writer/src/vrs_writer.cpp` に上記DataLayoutクラスを追加
2. **Python Binding**: pybind11でPython側から使用可能にする
3. **ROSbag変換スクリプト**: `rosbags-py`でROSbagを読み、VRSに書き込む
4. **テスト**: 変換したVRSファイルをC++ VRS Readerで読み取り、データ完全性を検証

---

**作成者**: Claude (Sonnet 4.5)
**バージョン**: 1.0
**最終更新**: 2025-11-19 09:26 UTC
