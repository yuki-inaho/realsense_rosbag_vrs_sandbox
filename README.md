# RealSense ROSbag to VRS Converter

**RealSense D435i ROSbagファイルをVRS (Virtual Reality Stream) 形式に変換し、カメラパラメータを含む情報を保存・再生できるツールセット**

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
- **圧縮指定**: 公式 PyVRS writer adapter 経由で `lz4` / `zstd` / `none` を指定
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
git clone https://github.com/yuki-inaho/realsense_rosbag_vrs_sandbox.git
cd realsense_rosbag_vrs_sandbox

# 2. Python環境セットアップ
uv sync --group dev

# 3. 変換実行
uv run python convert_to_vrs.py data/rosbag/sample.bag output.vrs --verbose

# 4. 検証実行
uv run python inspect_vrs.py output.vrs --verbose
```

---

## インストール

### 前提条件

- **Python 3.10以上**
- **uv** (Pythonパッケージマネージャ)
- **Linux環境推奨** (PyVRS はLinux/macOSのみサポート)

### Python環境とVRSライブラリ

```bash
# 1. uvインストール (未インストールの場合)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Python依存関係と開発ツール
uv sync --group dev
```

このリポジトリは自作 C++ writer や VRS submodule を保持しません。書き込みは PyPI `vrs>=1.2.2` に含まれる公式 PyVRS writer を `scripts/vrs_writer.py` の adapter 経由で使います。

主要依存の下限は `pyproject.toml` で管理しています: `vrs>=1.2.2`, `pyrealsense2>=2.58.2.10647`, `rosbags>=0.11.3`, `opencv-python>=5.0.0.93`, `numpy>=1.24.0,<2.3`。Python 3.10.6 継続のため NumPy は `<2.3` に固定しています。

### インストール確認

```bash
# ヘルプ表示（正常に動作すればOK）
uv run python convert_to_vrs.py --help
uv run python inspect_vrs.py --help
```

### テスト

```bash
# 実 rosbag 不要の通常回帰
uv run pytest -q -m "not integration"

# writer/converter/CLI focused regression
uv run pytest -q tests/test_official_pyvrs_writer.py tests/test_vrs_writer_adapter.py tests/test_converter_synthetic.py tests/test_cli_smoke.py

# 実 rosbag 検証は明示的に環境変数を指定
REALSENSE_ROSBAG_PATH=/absolute/path/to/sample.bag uv run pytest -q -m integration
```

---

## 使用方法

### 基本的なワークフロー

```bash
# Step 1: ROSbag を VRS に変換
uv run python convert_to_vrs.py data/rosbag/sample.bag output.vrs --verbose

# Step 2: VRS ファイルを検証
uv run python inspect_vrs.py output.vrs --verbose

# Step 3: 特定のストリームのみ表示
uv run python inspect_vrs.py output.vrs --stream 1001

# Step 4: JSON形式で出力
uv run python inspect_vrs.py output.vrs --json > config.json
```

### convert_to_vrs.py - ROSbag → VRS 変換

```bash
# 基本的な変換
uv run python convert_to_vrs.py INPUT.bag OUTPUT.vrs

# オプション
uv run python convert_to_vrs.py INPUT.bag OUTPUT.vrs \
    --compression zstd \  # 圧縮アルゴリズム (lz4/zstd/none)
    --verbose             # 詳細な進捗表示

# 使用例
uv run python convert_to_vrs.py data/rosbag/d435i_walking.bag data/vrs/output.vrs --verbose
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
  Compression:      output/input size ratio
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
│   ├── vrs_writer.py               # 公式 PyVRS writer adapter
│   └── vrs_reader.py               # VRS Reader ラッパー
├── tests/
│   ├── test_rosbag_to_vrs_converter.py
│   ├── test_vrs_writer.py
│   └── test_vrs_reader.py
├── docs/
│   ├── IMPLEMENTATION.md       # 実装詳細（mermaid図含む）
│   ├── VRS_API_CHEATSHEET.md   # VRS API チートシート
│   ├── rosbag_to_vrs_converter_design.md
│   ├── rosbag_to_vrs_mapping_spec.md
│   └── work_plan_rosbag_to_vrs_nov19_2025.md  # 2025年時点の履歴記録
└── tests/
    ├── test_official_pyvrs_writer.py
    ├── test_vrs_writer_adapter.py
    └── test_real_rosbag_integration.py
```

---

## ドキュメント

### 主要ドキュメント

- **[実装詳細 (IMPLEMENTATION.md)](docs/IMPLEMENTATION.md)**: システムアーキテクチャと実装の詳細説明（mermaid図含む）
- **[VRS API チートシート (VRS_API_CHEATSHEET.md)](docs/VRS_API_CHEATSHEET.md)**: VRS APIの逆引きリファレンス

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
**更新日:** 2026-07-08
**バージョン:** 1.1.0
