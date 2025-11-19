# ROSbag 20251119_112125.bag 構造分析

**注意**: 実際のROSbagファイルが現時点で入手できないため、RealSense D435iの標準的なトピック構造に基づいて文書化しています。

## 基本情報

- **デバイス**: Intel RealSense D435i
- **センサー構成**: RGB Camera + Depth Camera + IMU (Accel + Gyro)
- **想定Duration**: 数十秒～数分
- **想定Total messages**: 数百～数千メッセージ

## トピック一覧

### /device_0/sensor_1/Color_0/image/data

- **Type**: `sensor_msgs/msg/Image`
- **Count**: ~30 messages/sec（想定）
- **Resolution**: 1920 x 1080 (典型的な設定)
- **Encoding**: `rgb8` または `bgr8`
- **Data size**: 約6.2MB per frame (1920x1080x3 bytes)
- **説明**: RGBカラー画像ストリーム

### /device_0/sensor_0/Depth_0/image/data

- **Type**: `sensor_msgs/msg/Image`
- **Count**: ~30 messages/sec（想定）
- **Resolution**: 1280 x 720 (典型的な設定)
- **Encoding**: `16UC1` (16-bit unsigned, 1 channel)
- **Data size**: 約1.8MB per frame (1280x720x2 bytes)
- **説明**: 深度画像ストリーム（単位: mm）

### /device_0/sensor_1/Color_0/camera_info

- **Type**: `sensor_msgs/msg/CameraInfo`
- **Count**: ~30 messages/sec（Color画像と同期）
- **Intrinsics K**: 3x3行列（9要素）
  ```
  [fx,  0, cx]
  [ 0, fy, cy]
  [ 0,  0,  1]
  ```
  典型的な値（1920x1080の場合）:
  - fx, fy: ~1400-1450 pixels
  - cx: ~960 pixels (width/2)
  - cy: ~540 pixels (height/2)
- **Distortion D**: 5要素ベクトル (k1, k2, t1, t2, k3)
- **Distortion model**: `plumb_bob`（Brown-Conrady model）
- **説明**: RGBカメラの内部パラメータと歪み係数

### /device_0/sensor_0/Depth_0/camera_info

- **Type**: `sensor_msgs/msg/CameraInfo`
- **Count**: ~30 messages/sec（Depth画像と同期）
- **Intrinsics K**: 3x3行列（9要素）
  典型的な値（1280x720の場合）:
  - fx, fy: ~640-650 pixels
  - cx: ~640 pixels (width/2)
  - cy: ~360 pixels (height/2)
- **Distortion D**: 5要素ベクトル
- **Distortion model**: `plumb_bob`
- **説明**: 深度カメラの内部パラメータと歪み係数

### /device_0/sensor_2/Accel_0/imu/data

- **Type**: `sensor_msgs/msg/Imu`
- **Count**: ~63-250 messages/sec（IMUサンプリングレート）
- **Fields**:
  - `linear_acceleration`: Vector3 (x, y, z) [m/s²]
  - `angular_velocity`: Vector3 (x, y, z) [rad/s]（ジャイロデータと重複の可能性）
  - `orientation`: Quaternion (x, y, z, w)（通常は未使用: [0, 0, 0, 1]）
- **説明**: 加速度計データ

### /device_0/sensor_2/Gyro_0/imu/data

- **Type**: `sensor_msgs/msg/Imu`
- **Count**: ~200-400 messages/sec（IMUサンプリングレート）
- **Fields**:
  - `angular_velocity`: Vector3 (x, y, z) [rad/s]
  - `linear_acceleration`: Vector3 (x, y, z)（通常は未使用: [0, 0, 0]）
  - `orientation`: Quaternion (x, y, z, w)（通常は未使用: [0, 0, 0, 1]）
- **説明**: ジャイロスコープデータ

## データ特性

### 画像データ

- **同期**: Color画像とDepth画像は時刻同期されている
- **座標系**: Color座標系とDepth座標系は異なる（外部パラメータによる変換が必要）
- **深度範囲**: 0.3m～10m（典型的）
- **深度精度**: ~1mm @ 1m距離

### IMUデータ

- **同期**: Accelと Gyroは異なるサンプリングレートで独立
- **座標系**: IMU座標系はカメラ座標系と異なる（固定変換が存在）
- **ノイズ**: 低ノイズ（MEMS IMU）

## VRSマッピング要件

### ストリーム定義（Phase 4で実装予定）

- **Stream 1001**: Color Image (RGB Camera)
- **Stream 1002**: Depth Image (Depth Camera)
- **Stream 2001**: IMU Accelerometer
- **Stream 2002**: IMU Gyroscope

### 必須情報（VRSで保存すべき）

1. **カメラ内部パラメータ**: K行列、歪み係数D（Configuration Record）
2. **画像データ**: ピクセルデータ（Image Block）
3. **タイムスタンプ**: 各メッセージの時刻（Data Record）
4. **IMUデータ**: 加速度、角速度（Data Record）

### 推奨情報

1. **フレームID**: ROS座標系の識別子
2. **シーケンス番号**: メッセージ順序
3. **外部パラメータ**: Color-Depth間の変換行列

### オプション情報

1. **メッセージヘッダー**: ROSメッセージの完全なヘッダー情報
2. **デバイスメタデータ**: シリアルナンバー、ファームウェアバージョン等

## 次のステップ

このトピック構造分析に基づいて、Phase 4（ROSbag→VRSマッピング設計）を実施します。
特に以下の設計が重要です：

1. DataLayout定義（カメラ内部パラメータ、IMUデータ）
2. ImageBlock統合（RGB/Depthピクセルデータ）
3. RecordableTypeId選定（ForwardCamera, DepthSensor, MotionSensor）
