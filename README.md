# RealSense ROSbag to VRS Converter

**RealSense D435i ROSbagファイルをVRS (Virtual Reality Stream) 形式に変換し、カメラパラメータを含む完全な情報を保存・再生できるツールセット**

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)

## 目次

- [概要](#概要)
- [クイックスタート](#クイックスタート)
- [インストール](#インストール)
- [使用方法](#使用方法)
- [データ構造](#データ構造)
- [ドキュメント](#ドキュメント)

---

## 概要

このプロジェクトは、RealSense D435iで撮影したRGB-Dデータ（ROSbag形式）を、Meta社が開発したVRS (Virtual Reality Stream) 形式に変換するツールです。VRS形式への変換により、AR/VRエコシステム（Meta Quest、Project Aria等）との互換性を確保し、効率的なストレージと再生を実現します。

### 主な機能

- **ROSbag → VRS 変換**: ROS1/ROS2両対応、Color + Depth 画像
- **カメラパラメータ保存**: K行列、歪み係数、distortion model
- **高効率圧縮**: LZ4/ZSTD対応、圧縮率 30-40%
- **VRS ファイル検証**: ストリーム情報、Configuration、レコード数
- **ROSbag同等の情報再生**: すべてのカメラパラメータを復元可能

### 対応データ

| データ種別 | ステータス | ストリームID | 説明 |
|-----------|----------|------------|------|
| Color Image | 実装済み | 1001 | RGB画像 + カメラ内部パラメータ + StreamInfo (fps, encoding) |
| Depth Image | 実装済み | 1002 | Depth画像 + depth_scale + カメラパラメータ + StreamInfo (fps, encoding) |
| Transform | 実装済み | 1005, 1006 | カメラ外部パラメータ (Depth, Color) |
| IMU (Accel) | 実装済み | 1003 | 加速度センサー + StreamInfo (fps, encoding) |
| IMU (Gyro) | 実装済み | 1004 | ジャイロセンサー + StreamInfo (fps, encoding) |
| Device Info | 実装済み | 2001 | デバイス情報 (名称, SN, FW version等) |
| Sensor Info | 実装済み | 2002-2004 | センサー情報 (Stereo/RGB/Motion Module) |
| Options | 実装済み | 2005 | センサー設定オプション (25オプション: Exposure, Gain, Laser Power等) |
| Metadata | 未実装 | - | 画像・IMUメタデータ (14,219メッセージ) |

---

## クイックスタート

```bash
# 1. リポジトリクローン
git clone --recursive https://github.com/yuki-inaho/realsense_rosbag_vrs_sandbox.git
cd realsense_rosbag_vrs_sandbox

# 2. システム依存関係インストール
sudo apt-get install -y build-essential cmake ninja-build \
    libboost-all-dev liblz4-dev libzstd-dev libjpeg-dev \
    libeigen3-dev libgtest-dev pybind11-dev

# 3. Python環境セットアップ
uv sync
cd third/vrs && git submodule update --init --recursive
mkdir -p build && cd build
cmake .. -GNinja -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=../../vrs_install
ninja && ninja install
cd ../../..

# 4. pyvrs_writer ビルド
cd pyvrs_writer && uv pip install -e . && cd ..

# 5. 変換実行
./convert_to_vrs.py data/rosbag/sample.bag output.vrs --verbose

# 6. 検証実行
./inspect_vrs.py output.vrs --verbose
```

---

## インストール

### 前提条件

- **Python 3.10以上**
- **uv** (Pythonパッケージマネージャ)
- **Linux環境推奨** (PyVRS はLinux/macOSのみサポート)

### システム依存関係

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y \
    build-essential cmake ninja-build \
    libboost-all-dev liblz4-dev libzstd-dev \
    libjpeg-dev libeigen3-dev libgtest-dev \
    pybind11-dev

# macOS (Homebrew)
brew install cmake ninja boost lz4 zstd jpeg eigen pybind11
```

### Python環境とVRSライブラリ

```bash
# 1. uvインストール (未インストールの場合)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Python依存関係
uv sync

# 3. VRS C++ライブラリのビルド
cd third/vrs
git submodule update --init --recursive
mkdir -p build && cd build
cmake .. -GNinja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=../../vrs_install
ninja
ninja install
cd ../../..

# 4. pyvrs_writer のビルド・インストール
cd pyvrs_writer
uv pip install -e .
cd ..
```

### インストール確認

```bash
# ヘルプ表示（正常に動作すればOK）
./convert_to_vrs.py --help
./inspect_vrs.py --help
```

---

## 使用方法

### 基本的なワークフロー

```bash
# Step 1: ROSbag を VRS に変換
./convert_to_vrs.py data/rosbag/sample.bag output.vrs --verbose

# Step 2: VRS ファイルを検証
./inspect_vrs.py output.vrs --verbose

# Step 3: 特定のストリームのみ表示
./inspect_vrs.py output.vrs --stream 1001

# Step 4: JSON形式で出力
./inspect_vrs.py output.vrs --json > config.json
```

### convert_to_vrs.py - ROSbag → VRS 変換

```bash
# 基本的な変換
./convert_to_vrs.py INPUT.bag OUTPUT.vrs

# オプション
./convert_to_vrs.py INPUT.bag OUTPUT.vrs \
    --compression zstd \  # 圧縮アルゴリズム (lz4/zstd/none)
    --verbose             # 詳細な進捗表示

# 使用例
./convert_to_vrs.py data/rosbag/d435i_walking.bag data/vrs/output.vrs --verbose
```

**出力例:**

```
======================================================================
Converting ROSbag to VRS
======================================================================
  Input:       data/rosbag/d435i_walking.bag
  Output:      data/vrs/output.vrs
  Compression: lz4
  Phase:       4A (Color + Depth)
----------------------------------------------------------------------
Created stream 1001: RealSense_D435i_Color|id:1001
Created stream 1002: RealSense_D435i_Depth|id:1002
Cached CameraInfo from /device_0/sensor_0/Depth_0/info/camera_info
Cached CameraInfo from /device_0/sensor_1/Color_0/info/camera_info
Wrote Configuration for stream 1001 (Color): 640x480
Wrote Configuration for stream 1002 (Depth): 1280x720

======================================================================
Conversion Complete!
======================================================================
  Input size:       689.33 MB
  Output size:      253.03 MB
  Compression:      36.71%
  Total messages:   521
  - Color stream:   260 records
  - Depth stream:   261 records
  Conversion time:  18.81s
```

### inspect_vrs.py - VRS ファイル検証

```bash
# 基本情報表示
./inspect_vrs.py OUTPUT.vrs

# 詳細情報表示（カメラ行列含む）
./inspect_vrs.py OUTPUT.vrs --verbose

# 特定のストリームのみ
./inspect_vrs.py OUTPUT.vrs --stream 1001

# JSON形式で出力
./inspect_vrs.py OUTPUT.vrs --json > config.json
```

**出力例:**

```
======================================================================
VRS File Inspection
======================================================================
  File:         output.vrs
  Size:         253.03 MB
  Total Streams: 2

======================================================================
Stream 1/2: ID 1001
======================================================================
  Record Count: 260

  Configuration:
    Resolution:   640x480
    Encoding:     rgb8

  Camera Intrinsics:
    fx: 616.52, fy: 616.65
    cx: 315.87, cy: 244.28
    Distortion:   [0.000000, 0.000000, 0.000000, 0.000000, 0.000000]
    Model:        Brown Conrady

  Timestamp Range:
    First: 1543155318.345
    Last:  1543155319.356
```

---

## データ構造

### ROSbag → VRS マッピング

| ROSbag トピック | VRS Stream | 説明 |
|----------------|-----------|------|
| `/device_0/sensor_1/Color_0/image/data` | 1001 (Data) | RGB画像データ |
| `/device_0/sensor_1/Color_0/info/camera_info` | 1001 (Config) | カメラ内部パラメータ |
| `/device_0/sensor_0/Depth_0/image/data` | 1002 (Data) | Depth画像データ |
| `/device_0/sensor_0/Depth_0/info/camera_info` | 1002 (Config) | Depth カメラパラメータ |

### Configuration レコード構造

#### Color Stream (1001)

```json
{
  "width": 640,
  "height": 480,
  "encoding": "rgb8",
  "camera_k": [fx, 0, cx, 0, fy, cy, 0, 0, 1],
  "camera_d": [k1, k2, p1, p2, k3],
  "distortion_model": "Brown Conrady",
  "frame_id": ""
}
```

#### Depth Stream (1002)

```json
{
  "width": 1280,
  "height": 720,
  "encoding": "16UC1",
  "camera_k": [fx, 0, cx, 0, fy, cy, 0, 0, 1],
  "camera_d": [k1, k2, p1, p2, k3],
  "distortion_model": "Brown Conrady",
  "depth_scale": 0.001,
  "frame_id": ""
}
```

### プロジェクト構造

```
realsense_rosbag_vrs_sandbox/
├── convert_to_vrs.py          # 変換ツール（ユーザー向け）
├── inspect_vrs.py              # 検証ツール（ユーザー向け）
├── README.md                   # このファイル
├── scripts/
│   ├── rosbag_to_vrs_converter.py  # 変換コアロジック
│   ├── vrs_writer.py               # VRS Writer ラッパー
│   └── vrs_reader.py               # VRS Reader ラッパー
├── tests/
│   ├── test_rosbag_to_vrs_converter.py
│   ├── test_vrs_writer.py
│   └── test_vrs_reader.py
├── pyvrs_writer/               # C++ VRS Writer Python bindings
│   ├── src/                    # C++ implementation
│   ├── include/                # Header files
│   ├── python/                 # Python package
│   └── setup.py
├── docs/
│   ├── IMPLEMENTATION.md       # 実装詳細（mermaid図含む）
│   ├── VRS_API_CHEATSHEET.md   # VRS API チートシート
│   ├── rosbag_to_vrs_converter_design.md
│   ├── rosbag_to_vrs_mapping_spec.md
│   └── work_plan_rosbag_to_vrs_nov19_2025.md  # 作業計画書（トラブルシューティング・開発者情報含む）
└── third/
    └── vrs/                    # VRS C++ library (submodule)
```

---

## ドキュメント

### 主要ドキュメント

- **[実装詳細 (IMPLEMENTATION.md)](docs/IMPLEMENTATION.md)**: システムアーキテクチャと実装の詳細説明（mermaid図含む）
- **[VRS API チートシート (VRS_API_CHEATSHEET.md)](docs/VRS_API_CHEATSHEET.md)**: VRS APIの逆引きリファレンス
- **[作業計画書 (work_plan_rosbag_to_vrs_nov19_2025.md)](docs/work_plan_rosbag_to_vrs_nov19_2025.md)**: 開発プロセス全体の記録、トラブルシューティング、テスト方法

### 設計ドキュメント

- [設計書 (rosbag_to_vrs_converter_design.md)](docs/rosbag_to_vrs_converter_design.md): 変換ロジックの詳細設計
- [マッピング仕様 (rosbag_to_vrs_mapping_spec.md)](docs/rosbag_to_vrs_mapping_spec.md): ROSbag → VRS データマッピング詳細

---

## ライセンス

本プロジェクトは以下のライセンスに準じます：

- **VRS C++ Library**: Apache 2.0 (Meta Reality Labs Research)
- **PyVRS**: Apache 2.0
- **本プロジェクトコード**: Apache 2.0

---

## 謝辞

- [VRS (Virtual Reality Stream)](https://github.com/facebookresearch/vrs) - Meta Reality Labs Research
- [PyVRS](https://github.com/facebookresearch/pyvrs) - Python bindings for VRS
- [rosbags](https://gitlab.com/ternaris/rosbags) - Pure Python ROSbag library

---

**作成日:** 2025-11-19
**更新日:** 2025-11-19
**バージョン:** 1.0.0
