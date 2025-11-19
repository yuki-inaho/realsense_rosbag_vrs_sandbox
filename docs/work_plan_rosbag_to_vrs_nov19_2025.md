# 作業計画書 兼 記録書: ROSbag to VRS 変換システム実装

---

**日付：** `2025年11月19日`
**作業ディレクトリ・リポジトリ:** `/home/user/realsense_vrs_sandbox` (yuki-inaho/realsense_vrs_sandbox)
**作業者：** `[作業者名を記入]`

---

## 1. 作業目的

本作業は、RealSense D435iで撮影したRGB-D-IR + IMUデータを含むROSbag形式ファイルを、Meta社が開発したVRS (Virtual Reality Stream) 形式に変換し、VRSエコシステムでの活用を可能にすることを目的とします。

### 背景と意義

**現状の課題:**
- ROSbag形式はROS環境に依存し、AR/VRエコシステムとの互換性が低い
- Meta Quest、Project Ariaなどのデバイスとのデータ共有が困難
- VRSの高効率な圧縮・ランダムアクセス機能を活用できていない

**VRS形式の利点:**
- **高効率ストレージ**: lz4/zstd圧縮によるファイルサイズ削減
- **マルチストリーム対応**: 複数センサーを独立したストリームとして管理
- **タイムスタンプ同期**: 共通時間軸での高精度な時系列データ管理
- **AR/VR互換性**: Meta Quest、Project Ariaとのシームレスなデータ交換
- **ランダムアクセス**: 効率的な任意時刻へのシーク機能

### 達成目標

*   **目標1:** PyVRS環境のセットアップと基本動作確認（サンプルVRSファイルの作成・読み込み）
*   **目標2:** ROSbag → VRS データマッピング仕様の策定と文書化
*   **目標3:** TDD方式でのVRS Writer/Readerモジュール実装（100%テストカバレッジ目標）
*   **目標4:** ROSbag to VRS変換スクリプトの実装と動作検証
*   **目標5:** VRS再生・検証ツールの実装

---

## 2. 前提知識と技術スタック

### VRS (Virtual Reality Stream) フォーマット概要

**開発元:** Meta Reality Labs Research
**ライセンス:** Apache 2.0
**公式ドキュメント:** https://facebookresearch.github.io/vrs/

**VRSの基本構造:**

```
VRS File
├── Stream 0 (例: RGB Camera)
│   ├── Configuration Record (1個) - センサー設定情報
│   ├── State Record (0-N個) - ストリーム状態
│   └── Data Records (多数) - タイムスタンプ付きセンサーデータ
├── Stream 1 (例: Depth Camera)
│   ├── Configuration Record
│   └── Data Records
├── Stream 2 (例: IMU Accelerometer)
│   ├── Configuration Record
│   └── Data Records
└── Stream 3 (例: IMU Gyroscope)
    ├── Configuration Record
    └── Data Records
```

**レコードタイプ:**
- `Configuration`: ストリームの設定情報（解像度、フレームレート、キャリブレーション等）
- `State`: ストリームの状態変化（露出変更、ゲイン調整等）
- `Data`: 実際のセンサーデータ（画像、IMU測定値等）

**コンテンツブロック:**
- `Metadata Block`: JSON形式のメタデータ
- `Image Block`: 生画像またはJPEG/PNG圧縮画像
- `Audio Block`: 音声サンプル
- `Custom Block`: カスタムバイナリデータ

### PyVRS API概要

**インストール:**
```bash
pip install vrs  # Linux/macOS対応、Windows版は開発中
```

**主要モジュール（推定）:**
- `vrs.RecordFileWriter`: VRSファイル書き込み
- `vrs.RecordFileReader`: VRSファイル読み込み
- `vrs.StreamId`: ストリーム識別子
- `vrs.RecordType`: レコード種別（Configuration/State/Data）
- `vrs.DataLayout`: データ構造定義

### RealSense D435i センサー構成

**対象ROSbagトピック:**
- `/device_0/sensor_1/Color_0/image/data` - RGB画像 (sensor_msgs/msg/Image)
- `/device_0/sensor_0/Depth_0/image/data` - Depth画像 (sensor_msgs/msg/Image)
- `/device_0/sensor_2/Accel_0/imu/data` - 加速度計 (sensor_msgs/msg/Imu)
- `/device_0/sensor_2/Gyro_0/imu/data` - ジャイロスコープ (sensor_msgs/msg/Imu)
- （オプション）IR画像トピック（存在する場合）

**データ特性:**
- RGB: 30 Hz, 640x480 or 1920x1080 (bagによる)
- Depth: 30 Hz, 640x480
- Accel: ~63-250 Hz (設定依存)
- Gyro: ~200-400 Hz (設定依存)

### 技術スタック

- **言語:** Python 3.9+
- **パッケージ管理:** uv
- **タスクランナー:** justfile (必要に応じて)
- **テストフレームワーク:** pytest, pytest-cov
- **型チェック:** mypy (strict mode)
- **リンター/フォーマッター:** ruff
- **主要ライブラリ:**
  - `vrs` (PyVRS) - VRS読み書き
  - `rosbags` - ROSbag読み込み
  - `numpy` - 数値計算
  - `opencv-python` - 画像処理（必要に応じて）

---

## 3. 作業内容

### フェーズ 1: 環境構築と調査 (見積: 2.0h)

このフェーズでは、PyVRS環境をセットアップし、基本的なVRSファイルの作成・読み込みを確認します。また、PyVRS APIの詳細を調査し、実装方針を固めます。

#### 手順 1.1: PyVRSインストールとバージョン確認

- [ ] 🖐 **操作**: uv環境にPyVRSをインストール
  ```bash
  cd /home/user/realsense_vrs_sandbox
  uv pip install vrs
  ```

- [ ] 🔎 **確認**: インストール成功とバージョン表示
  ```bash
  uv run python -c "import vrs; print(f'PyVRS version: {vrs.__version__ if hasattr(vrs, \"__version__\") else \"installed\"}')"
  ```
  **期待結果:** `PyVRS version: 1.2.1` または `installed` と表示され、ImportErrorが発生しないこと

- [ ] 🧪 **テスト**: PyVRSモジュールのインポート可能性確認
  ```bash
  # tests/test_vrs_import.pyを作成してテスト
  uv run pytest tests/test_vrs_import.py -v
  ```
  **期待:** 最初は`tests/test_vrs_import.py`が存在しないため失敗 → 作成後に成功

- [ ] 🛠 **エラー時対処**:
  - `ERROR: Could not find a version that satisfies the requirement vrs`:
    - Windowsの場合はソースビルドが必要（`git clone --recursive https://github.com/facebookresearch/pyvrs.git` → `python -m pip install -e .`）
  - `ImportError: libvrs.so: cannot open shared object file`:
    - システムライブラリ依存関係の不足。`apt-get install -y liblz4-dev libzstd-dev` 等を実行
  - Python 3.8以下の環境: Python 3.9+にアップグレード必須

#### 手順 1.2: PyVRS APIドキュメント調査とモジュール構造把握

- [ ] 🖐 **操作**: PyVRSの利用可能なクラスとメソッドを列挙
  ```bash
  uv run python -c "import vrs; print(dir(vrs))"
  ```

- [ ] 🔎 **確認**: 以下のクラス/関数が存在することを確認（存在するものを記録）
  - `RecordFileWriter` または類似の書き込みクラス
  - `RecordFileReader` または類似の読み込みクラス
  - `StreamId` または ストリーム識別機構
  - その他利用可能なAPI

  **期待結果:** 上記のクラスまたは類似機能のクラス名をリストアップし、`docs/pyvrs_api_investigation.md`に記録

- [ ] 🧪 **テスト**: API調査スクリプトの作成と実行
  ```bash
  # scripts/investigate_pyvrs_api.py を作成
  uv run python scripts/investigate_pyvrs_api.py > docs/pyvrs_api_investigation.md
  ```
  **期待:** PyVRSの全クラス・メソッド・定数の一覧がMarkdownファイルに出力される

- [ ] 🛠 **エラー時対処**:
  - `AttributeError: module 'vrs' has no attribute 'RecordFileWriter'`:
    - PyVRSのバージョンやビルド方法によりAPIが異なる可能性。公式ドキュメント https://pyvrs.readthedocs.io/ を再確認
  - APIが空またはほぼ空: C++バインディングのビルドに失敗している可能性。ソースからの再ビルドを検討

#### 手順 1.3: 最小限のVRSファイル作成テスト（Hello World）

- [ ] 🖐 **操作**: 簡単なVRSファイルを作成するPythonスクリプト作成
  ```bash
  # scripts/create_sample_vrs.py を作成
  # 以下のような最小限のVRSファイルを作成:
  # - 1つのストリーム（例: テストデータストリーム）
  # - Configurationレコード1個
  # - Dataレコード数個（タイムスタンプ付き）
  ```

- [ ] 🔎 **確認**: VRSファイルが生成され、ファイルサイズが0でないこと
  ```bash
  uv run python scripts/create_sample_vrs.py
  ls -lh data/test_sample.vrs
  file data/test_sample.vrs
  ```
  **期待結果:** `data/test_sample.vrs` が存在し、数KB以上のサイズを持つこと

- [ ] 🧪 **テスト**: VRSファイル作成のテストケース作成
  ```bash
  # tests/test_create_sample_vrs.py を作成
  # - ファイルが作成されること
  # - ファイルサイズが0でないこと
  # - VRS形式として認識されること（可能であれば）
  uv run pytest tests/test_create_sample_vrs.py -v
  ```
  **期待:** RED → GREEN (最初は実装なしで失敗 → 実装後に成功)

- [ ] 🛠 **エラー時対処**:
  - `TypeError: 'NoneType' object is not callable`: PyVRS APIの使用方法が誤っている可能性。公式サンプルコードを参照
  - `RuntimeError: Failed to create VRS file`: 書き込み権限の問題。`chmod 755 data/` を実行
  - VRSファイルが0バイト: レコード書き込み後にファイルをクローズしていない可能性。`close()`メソッドの呼び出しを確認

#### 手順 1.4: VRSファイル読み込みテスト

- [ ] 🖐 **操作**: 手順1.3で作成したVRSファイルを読み込むスクリプト作成
  ```bash
  # scripts/read_sample_vrs.py を作成
  # - VRSファイルを開く
  # - ストリーム一覧を取得
  # - レコード数をカウント
  # - 各レコードのタイムスタンプを表示
  ```

- [ ] 🔎 **確認**: ストリーム情報とレコード情報が正しく読み取れること
  ```bash
  uv run python scripts/read_sample_vrs.py data/test_sample.vrs
  ```
  **期待結果:**
  ```
  VRS file: data/test_sample.vrs
  Streams: 1
  Stream 0: [ストリーム名/ID]
    Configuration records: 1
    Data records: [作成した個数]
    Timestamps: [0.0, 0.033, 0.066, ...]
  ```

- [ ] 🧪 **テスト**: VRSファイル読み込みのテストケース作成
  ```bash
  # tests/test_read_sample_vrs.py を作成
  # - ファイルが正しく開けること
  # - ストリーム数が期待値と一致すること
  # - レコード数が期待値と一致すること
  uv run pytest tests/test_read_sample_vrs.py -v
  ```
  **期待:** RED → GREEN

- [ ] 🛠 **エラー時対処**:
  - `FileNotFoundError`: `data/test_sample.vrs`のパスを確認
  - `RuntimeError: Invalid VRS file`: ファイルが破損している可能性。手順1.3を再実行
  - レコード数が0: 書き込み時にデータレコードが正しく追加されていない可能性

#### 手順 1.5: ROSbag → VRS データマッピング仕様書の作成

- [ ] 🖐 **操作**: マッピング仕様書をMarkdownで作成
  ```bash
  # docs/rosbag_to_vrs_mapping_spec.md を作成
  ```

  **記載内容:**
  ```markdown
  # ROSbag to VRS データマッピング仕様

  ## ストリーム設計

  | VRS Stream ID | センサー種別 | ROSbagトピック | データ型 | サンプリングレート |
  |--------------|------------|---------------|--------|------------------|
  | 1001 | RGB Camera | /device_0/sensor_1/Color_0/image/data | sensor_msgs/msg/Image | ~30 Hz |
  | 1002 | Depth Camera | /device_0/sensor_0/Depth_0/image/data | sensor_msgs/msg/Image | ~30 Hz |
  | 2001 | IMU Accel | /device_0/sensor_2/Accel_0/imu/data | sensor_msgs/msg/Imu | ~63-250 Hz |
  | 2002 | IMU Gyro | /device_0/sensor_2/Gyro_0/imu/data | sensor_msgs/msg/Imu | ~200-400 Hz |

  ## Configurationレコード内容

  ### RGB Camera (Stream 1001)
  - width: 画像幅
  - height: 画像高さ
  - encoding: RGB8 / BGR8 等
  - frame_id: ROSフレームID

  ### Depth Camera (Stream 1002)
  - width: 画像幅
  - height: 画像高さ
  - encoding: 16UC1 等
  - depth_scale: メートル変換係数

  ### IMU (Stream 2001, 2002)
  - sensor_name: "Accel" / "Gyro"
  - frame_id: ROSフレームID

  ## Dataレコード内容

  ### 画像データ (Stream 1001, 1002)
  - timestamp: ROSタイムスタンプ (nanoseconds)
  - image_data: 生画像バイト列またはJPEG圧縮データ

  ### IMUデータ (Stream 2001, 2002)
  - timestamp: ROSタイムスタンプ (nanoseconds)
  - linear_acceleration: [x, y, z] (m/s²) - Accelのみ
  - angular_velocity: [x, y, z] (rad/s) - Gyroのみ

  ## タイムスタンプ変換

  - ROSタイムスタンプ (nanoseconds since epoch) → VRSタイムスタンプ
  - 基準時刻: ROSbag開始時刻を0秒とする相対時刻に変換
  ```

- [ ] 🔎 **確認**: 仕様書が完成し、全トピックのマッピングが明記されていること
  ```bash
  cat docs/rosbag_to_vrs_mapping_spec.md
  ```
  **期待結果:** 上記テーブルと説明が含まれた完全な仕様書

- [ ] 🧪 **テスト**: 仕様書の存在確認（ドキュメントテスト）
  ```bash
  test -f docs/rosbag_to_vrs_mapping_spec.md && echo "仕様書作成完了" || echo "仕様書未作成"
  ```
  **期待:** `仕様書作成完了` と表示

- [ ] 🛠 **エラー時対処**:
  - トピック名が異なる場合: `extract_realsense_data.py`で実際のROSbagのトピック一覧を確認し、仕様書を更新
  - Stream IDの重複: 各ストリームに一意のIDを割り当てる（1000番台: カメラ、2000番台: IMU等）

---

### フェーズ 2: VRS Writerモジュール実装 (TDD) (見積: 4.0h)

このフェーズでは、VRSファイルを書き込むための再利用可能なモジュール `scripts/vrs_writer.py` をTDD方式で実装します。

#### 手順 2.1: VRS Writerモジュールのインターフェース設計

- [ ] 🖐 **操作**: VRS Writerのクラス設計をドキュメント化
  ```bash
  # docs/vrs_writer_design.md を作成
  ```

  **記載内容:**
  ```markdown
  # VRS Writer モジュール設計

  ## クラス: VRSWriter

  ### 責務
  - VRSファイルの作成と管理
  - ストリームの追加
  - Configurationレコードの書き込み
  - Dataレコードの書き込み
  - ファイルのクローズ

  ### インターフェース

  #### `__init__(self, filepath: Path)`
  - VRSファイルを作成・オープン

  #### `add_stream(self, stream_id: int, stream_name: str) -> None`
  - 新しいストリームを追加

  #### `write_configuration(self, stream_id: int, config_data: dict[str, Any]) -> None`
  - Configurationレコードを書き込み

  #### `write_data(self, stream_id: int, timestamp: float, data: bytes | dict) -> None`
  - Dataレコードを書き込み（タイムスタンプ付き）

  #### `close(self) -> None`
  - VRSファイルをクローズ

  #### コンテキストマネージャ対応
  - `__enter__` / `__exit__` 実装

  ### 使用例

  ```python
  from scripts.vrs_writer import VRSWriter
  from pathlib import Path

  with VRSWriter(Path("output.vrs")) as writer:
      writer.add_stream(1001, "RGB Camera")
      writer.write_configuration(1001, {"width": 640, "height": 480})
      writer.write_data(1001, 0.0, image_bytes)
      writer.write_data(1001, 0.033, image_bytes2)
  ```
  ```

- [ ] 🔎 **確認**: 設計書が完成していること
  ```bash
  cat docs/vrs_writer_design.md
  ```

- [ ] 🧪 **テスト**: 設計書の存在確認
  ```bash
  test -f docs/vrs_writer_design.md && echo "設計書完了" || echo "設計書未作成"
  ```

- [ ] 🛠 **エラー時対処**:
  - PyVRS APIが設計と合わない場合: 手順1.2の調査結果を基に設計を修正

#### 手順 2.2: VRS Writerテストケース作成 (RED)

- [ ] 🖐 **操作**: `tests/test_vrs_writer.py` を作成
  ```python
  # tests/test_vrs_writer.py
  import pytest
  from pathlib import Path
  from scripts.vrs_writer import VRSWriter

  def test_vrs_writer_initialization(tmp_path):
      """VRSWriterが正しく初期化されること"""
      vrs_file = tmp_path / "test.vrs"
      writer = VRSWriter(vrs_file)
      assert writer is not None
      writer.close()
      assert vrs_file.exists()

  def test_vrs_writer_context_manager(tmp_path):
      """コンテキストマネージャとして使用できること"""
      vrs_file = tmp_path / "test.vrs"
      with VRSWriter(vrs_file) as writer:
          assert writer is not None
      assert vrs_file.exists()

  def test_add_stream(tmp_path):
      """ストリームを追加できること"""
      vrs_file = tmp_path / "test.vrs"
      with VRSWriter(vrs_file) as writer:
          writer.add_stream(1001, "Test Stream")
          # ストリーム追加の検証方法は実装依存

  def test_write_configuration(tmp_path):
      """Configurationレコードを書き込めること"""
      vrs_file = tmp_path / "test.vrs"
      with VRSWriter(vrs_file) as writer:
          writer.add_stream(1001, "Test Stream")
          config = {"width": 640, "height": 480}
          writer.write_configuration(1001, config)

  def test_write_data(tmp_path):
      """Dataレコードを書き込めること"""
      vrs_file = tmp_path / "test.vrs"
      with VRSWriter(vrs_file) as writer:
          writer.add_stream(1001, "Test Stream")
          writer.write_data(1001, 0.0, b"test data")
          writer.write_data(1001, 0.033, b"test data 2")

  def test_multiple_streams(tmp_path):
      """複数のストリームを扱えること"""
      vrs_file = tmp_path / "test.vrs"
      with VRSWriter(vrs_file) as writer:
          writer.add_stream(1001, "Stream 1")
          writer.add_stream(1002, "Stream 2")
          writer.write_data(1001, 0.0, b"data1")
          writer.write_data(1002, 0.0, b"data2")
  ```

- [ ] 🔎 **確認**: テストが失敗すること (RED)
  ```bash
  uv run pytest tests/test_vrs_writer.py -v
  ```
  **期待結果:** `ModuleNotFoundError: No module named 'scripts.vrs_writer'` または全テスト失敗

- [ ] 🧪 **テスト**: RED状態の確認
  ```bash
  uv run pytest tests/test_vrs_writer.py -v 2>&1 | grep -E "(FAILED|ERROR)" && echo "RED確認完了" || echo "すでに実装済み？"
  ```

- [ ] 🛠 **エラー時対処**:
  - テストが通ってしまう場合: 既に実装が存在している可能性。`scripts/vrs_writer.py`の存在確認

#### 手順 2.3: VRS Writer実装 (GREEN)

- [ ] 🖐 **操作**: `scripts/vrs_writer.py` を実装
  ```python
  # scripts/vrs_writer.py
  """VRS file writer module for creating VRS files from sensor data."""

  from pathlib import Path
  from typing import Any
  import vrs  # PyVRSのインポート（実際のAPIに応じて調整）

  class VRSWriter:
      """VRS file writer with context manager support."""

      def __init__(self, filepath: Path) -> None:
          """Initialize VRS writer.

          Args:
              filepath: Path to the VRS file to create
          """
          self.filepath = filepath
          # PyVRS APIを使用してファイルを作成
          # 実際のAPIに応じて実装

      def __enter__(self) -> "VRSWriter":
          """Context manager entry."""
          return self

      def __exit__(self, exc_type, exc_val, exc_tb) -> None:
          """Context manager exit."""
          self.close()

      def add_stream(self, stream_id: int, stream_name: str) -> None:
          """Add a new stream to the VRS file.

          Args:
              stream_id: Unique stream identifier
              stream_name: Human-readable stream name
          """
          # 実装
          pass

      def write_configuration(self, stream_id: int, config_data: dict[str, Any]) -> None:
          """Write a configuration record.

          Args:
              stream_id: Target stream ID
              config_data: Configuration parameters as dictionary
          """
          # 実装
          pass

      def write_data(self, stream_id: int, timestamp: float, data: bytes | dict) -> None:
          """Write a data record.

          Args:
              stream_id: Target stream ID
              timestamp: Timestamp in seconds
              data: Data payload (bytes or dict)
          """
          # 実装
          pass

      def close(self) -> None:
          """Close the VRS file."""
          # 実装
          pass
  ```

- [ ] 🔎 **確認**: テストが成功すること (GREEN)
  ```bash
  uv run pytest tests/test_vrs_writer.py -v --cov=scripts/vrs_writer --cov-report=term-missing
  ```
  **期待結果:** 全テストPASS、カバレッジ80%以上

- [ ] 🧪 **テスト**: GREEN状態の確認
  ```bash
  uv run pytest tests/test_vrs_writer.py -v 2>&1 | grep "passed" && echo "GREEN達成" || echo "まだRED"
  ```

- [ ] 🛠 **エラー時対処**:
  - `AttributeError`: PyVRS APIの使用方法を手順1.2の調査結果から再確認
  - テスト失敗: 一つずつテストを実行して原因を特定 (`pytest tests/test_vrs_writer.py::test_vrs_writer_initialization -v`)
  - カバレッジ不足: 未テストのブランチを特定し、テストケースを追加

#### 手順 2.4: VRS Writerリファクタリング (REFACTOR)

- [ ] 🖐 **操作**: コード品質向上
  ```bash
  # 型チェック
  uv run mypy scripts/vrs_writer.py --strict

  # リンター
  uv run ruff check scripts/vrs_writer.py

  # フォーマット
  uv run ruff format scripts/vrs_writer.py
  ```

- [ ] 🔎 **確認**: 警告・エラーが0件であること
  ```bash
  uv run mypy scripts/vrs_writer.py --strict && echo "型チェックOK"
  uv run ruff check scripts/vrs_writer.py && echo "リンターOK"
  ```

- [ ] 🧪 **テスト**: リファクタリング後もテストが通ること
  ```bash
  uv run pytest tests/test_vrs_writer.py -v
  ```
  **期待:** 全テストPASS（変更なし）

- [ ] 🛠 **エラー時対処**:
  - mypy警告: 型ヒントを追加・修正
  - ruff警告: コードスタイルを修正（未使用import削除、行長調整等）

---

### フェーズ 3: VRS Readerモジュール実装 (TDD) (見積: 3.0h)

このフェーズでは、VRSファイルを読み込むための再利用可能なモジュール `scripts/vrs_reader.py` をTDD方式で実装します。

#### 手順 3.1: VRS Readerテストケース作成 (RED)

- [ ] 🖐 **操作**: `tests/test_vrs_reader.py` を作成
  ```python
  # tests/test_vrs_reader.py
  import pytest
  from pathlib import Path
  from scripts.vrs_reader import VRSReader
  from scripts.vrs_writer import VRSWriter

  @pytest.fixture
  def sample_vrs_file(tmp_path):
      """テスト用のサンプルVRSファイルを作成"""
      vrs_file = tmp_path / "sample.vrs"
      with VRSWriter(vrs_file) as writer:
          writer.add_stream(1001, "Test Stream")
          writer.write_configuration(1001, {"key": "value"})
          writer.write_data(1001, 0.0, b"data1")
          writer.write_data(1001, 0.033, b"data2")
      return vrs_file

  def test_vrs_reader_initialization(sample_vrs_file):
      """VRSReaderが正しく初期化されること"""
      reader = VRSReader(sample_vrs_file)
      assert reader is not None
      reader.close()

  def test_vrs_reader_context_manager(sample_vrs_file):
      """コンテキストマネージャとして使用できること"""
      with VRSReader(sample_vrs_file) as reader:
          assert reader is not None

  def test_get_stream_ids(sample_vrs_file):
      """ストリームID一覧を取得できること"""
      with VRSReader(sample_vrs_file) as reader:
          stream_ids = reader.get_stream_ids()
          assert 1001 in stream_ids

  def test_read_configuration(sample_vrs_file):
      """Configurationレコードを読み込めること"""
      with VRSReader(sample_vrs_file) as reader:
          config = reader.read_configuration(1001)
          assert config["key"] == "value"

  def test_read_data_records(sample_vrs_file):
      """Dataレコードを読み込めること"""
      with VRSReader(sample_vrs_file) as reader:
          records = list(reader.read_data_records(1001))
          assert len(records) == 2
          assert records[0]["timestamp"] == 0.0
          assert records[0]["data"] == b"data1"
          assert records[1]["timestamp"] == 0.033
  ```

- [ ] 🔎 **確認**: テストが失敗すること (RED)
  ```bash
  uv run pytest tests/test_vrs_reader.py -v
  ```
  **期待結果:** `ModuleNotFoundError` または全テスト失敗

- [ ] 🧪 **テスト**: RED状態の確認

- [ ] 🛠 **エラー時対処**:
  - `sample_vrs_file` fixtureでエラー: VRSWriter実装を先に完成させる必要

#### 手順 3.2: VRS Reader実装 (GREEN)

- [ ] 🖐 **操作**: `scripts/vrs_reader.py` を実装
  ```python
  # scripts/vrs_reader.py
  """VRS file reader module for reading VRS files."""

  from pathlib import Path
  from typing import Iterator, Any
  import vrs

  class VRSReader:
      """VRS file reader with context manager support."""

      def __init__(self, filepath: Path) -> None:
          """Initialize VRS reader.

          Args:
              filepath: Path to the VRS file to read
          """
          self.filepath = filepath
          # PyVRS APIを使用してファイルを開く

      def __enter__(self) -> "VRSReader":
          """Context manager entry."""
          return self

      def __exit__(self, exc_type, exc_val, exc_tb) -> None:
          """Context manager exit."""
          self.close()

      def get_stream_ids(self) -> list[int]:
          """Get list of stream IDs in the file.

          Returns:
              List of stream IDs
          """
          # 実装
          pass

      def read_configuration(self, stream_id: int) -> dict[str, Any]:
          """Read configuration record for a stream.

          Args:
              stream_id: Target stream ID

          Returns:
              Configuration data as dictionary
          """
          # 実装
          pass

      def read_data_records(self, stream_id: int) -> Iterator[dict[str, Any]]:
          """Read data records for a stream.

          Args:
              stream_id: Target stream ID

          Yields:
              Data records with timestamp and data
          """
          # 実装
          pass

      def close(self) -> None:
          """Close the VRS file."""
          # 実装
          pass
  ```

- [ ] 🔎 **確認**: テストが成功すること (GREEN)
  ```bash
  uv run pytest tests/test_vrs_reader.py -v --cov=scripts/vrs_reader
  ```

- [ ] 🧪 **テスト**: GREEN状態の確認

- [ ] 🛠 **エラー時対処**:
  - `RuntimeError: Cannot read VRS file`: VRSWriterで作成したファイルが不正な可能性

#### 手順 3.3: VRS Readerリファクタリング (REFACTOR)

- [ ] 🖐 **操作**: コード品質向上
  ```bash
  uv run mypy scripts/vrs_reader.py --strict
  uv run ruff check scripts/vrs_reader.py
  uv run ruff format scripts/vrs_reader.py
  ```

- [ ] 🔎 **確認**: 警告・エラーが0件

- [ ] 🧪 **テスト**: リファクタリング後もテストが通ること
  ```bash
  uv run pytest tests/test_vrs_reader.py -v
  ```

- [ ] 🛠 **エラー時対処**: 手順2.4と同様

---

### フェーズ 4: ROSbag to VRS 変換スクリプト実装 (TDD) (見積: 5.0h)

このフェーズでは、ROSbagをVRSに変換するメインスクリプト `convert_rosbag_to_vrs.py` を実装します。

#### 手順 4.1: 変換ロジックモジュール設計

- [ ] 🖐 **操作**: `docs/rosbag_to_vrs_converter_design.md` を作成

  **記載内容:**
  ```markdown
  # ROSbag to VRS Converter 設計

  ## 処理フロー

  1. ROSbagファイルを開く（RosbagReaderを使用）
  2. VRSファイルを作成（VRSWriterを使用）
  3. マッピング仕様に基づいてストリームを作成
  4. 各トピックのConfigurationレコードを書き込み
  5. 全メッセージを時系列順に読み込み、対応するVRSストリームにDataレコードとして書き込み
  6. ファイルをクローズ

  ## モジュール: RosbagToVRSConverter (scripts/rosbag_to_vrs_converter.py)

  ### メソッド

  #### `__init__(self, rosbag_path: Path, vrs_path: Path, topic_mapping: dict)`
  - ROSbagとVRSのパス、トピックマッピングを受け取る

  #### `convert(self) -> None`
  - 変換処理のメインロジック

  #### `_create_streams(self) -> None`
  - マッピングに基づきVRSストリームを作成

  #### `_write_configurations(self) -> None`
  - 各ストリームのConfigurationレコードを書き込み

  #### `_convert_image_message(self, msg_data: dict) -> bytes`
  - ROSのImageメッセージをVRS用バイト列に変換

  #### `_convert_imu_message(self, msg_data: dict) -> dict`
  - ROSのImuメッセージをVRS用辞書に変換
  ```

- [ ] 🔎 **確認**: 設計書が完成していること

- [ ] 🧪 **テスト**: 設計書の存在確認

- [ ] 🛠 **エラー時対処**: なし（設計フェーズ）

#### 手順 4.2: Converterテストケース作成 (RED)

- [ ] 🖐 **操作**: `tests/test_rosbag_to_vrs_converter.py` を作成
  ```python
  # tests/test_rosbag_to_vrs_converter.py
  import pytest
  from pathlib import Path
  from scripts.rosbag_to_vrs_converter import RosbagToVRSConverter

  @pytest.fixture
  def rosbag_path(data_dir: Path) -> Path:
      """サンプルROSbagのパス"""
      return data_dir / "rosbag" / "d435i_walk_around.bag"

  @pytest.fixture
  def topic_mapping() -> dict:
      """トピックマッピング定義"""
      return {
          "/device_0/sensor_1/Color_0/image/data": {"stream_id": 1001, "type": "rgb"},
          "/device_0/sensor_0/Depth_0/image/data": {"stream_id": 1002, "type": "depth"},
          "/device_0/sensor_2/Accel_0/imu/data": {"stream_id": 2001, "type": "imu_accel"},
          "/device_0/sensor_2/Gyro_0/imu/data": {"stream_id": 2002, "type": "imu_gyro"},
      }

  def test_converter_initialization(rosbag_path, topic_mapping, tmp_path):
      """Converterが正しく初期化されること"""
      vrs_path = tmp_path / "output.vrs"
      converter = RosbagToVRSConverter(rosbag_path, vrs_path, topic_mapping)
      assert converter is not None

  def test_converter_convert(rosbag_path, topic_mapping, tmp_path):
      """変換処理が完了すること"""
      vrs_path = tmp_path / "output.vrs"
      converter = RosbagToVRSConverter(rosbag_path, vrs_path, topic_mapping)
      converter.convert()
      assert vrs_path.exists()
      assert vrs_path.stat().st_size > 0

  def test_converted_vrs_has_correct_streams(rosbag_path, topic_mapping, tmp_path):
      """変換後のVRSファイルが正しいストリーム数を持つこと"""
      from scripts.vrs_reader import VRSReader

      vrs_path = tmp_path / "output.vrs"
      converter = RosbagToVRSConverter(rosbag_path, vrs_path, topic_mapping)
      converter.convert()

      with VRSReader(vrs_path) as reader:
          stream_ids = reader.get_stream_ids()
          assert 1001 in stream_ids  # RGB
          assert 1002 in stream_ids  # Depth
          assert 2001 in stream_ids  # Accel
          assert 2002 in stream_ids  # Gyro
  ```

- [ ] 🔎 **確認**: テストが失敗すること (RED)
  ```bash
  uv run pytest tests/test_rosbag_to_vrs_converter.py -v
  ```

- [ ] 🧪 **テスト**: RED状態の確認

- [ ] 🛠 **エラー時対処**:
  - ROSbagファイルが存在しない: `data/rosbag/d435i_walk_around.bag` の存在を確認

#### 手順 4.3: Converter実装 (GREEN)

- [ ] 🖐 **操作**: `scripts/rosbag_to_vrs_converter.py` を実装
  ```python
  # scripts/rosbag_to_vrs_converter.py
  """ROSbag to VRS converter module."""

  from pathlib import Path
  from typing import Any
  import numpy as np

  from scripts.rosbag_reader import RosbagReader
  from scripts.vrs_writer import VRSWriter
  from scripts.timestamp_handler import ros_timestamp_to_seconds

  class RosbagToVRSConverter:
      """Convert ROSbag files to VRS format."""

      def __init__(
          self,
          rosbag_path: Path,
          vrs_path: Path,
          topic_mapping: dict[str, dict[str, Any]],
      ) -> None:
          """Initialize converter.

          Args:
              rosbag_path: Path to input ROSbag file
              vrs_path: Path to output VRS file
              topic_mapping: Mapping from ROS topics to VRS stream config
          """
          self.rosbag_path = rosbag_path
          self.vrs_path = vrs_path
          self.topic_mapping = topic_mapping

      def convert(self) -> None:
          """Execute conversion from ROSbag to VRS."""
          with RosbagReader(self.rosbag_path) as rosbag_reader, \
               VRSWriter(self.vrs_path) as vrs_writer:

              # ストリーム作成
              self._create_streams(vrs_writer)

              # Configuration書き込み
              self._write_configurations(vrs_writer, rosbag_reader)

              # データ変換・書き込み
              self._convert_data(vrs_writer, rosbag_reader)

      def _create_streams(self, vrs_writer: VRSWriter) -> None:
          """Create VRS streams based on topic mapping."""
          for topic, config in self.topic_mapping.items():
              stream_id = config["stream_id"]
              stream_name = config.get("type", topic)
              vrs_writer.add_stream(stream_id, stream_name)

      def _write_configurations(
          self,
          vrs_writer: VRSWriter,
          rosbag_reader: RosbagReader,
      ) -> None:
          """Write configuration records for each stream."""
          # 実装: 各ストリームの設定情報を書き込み
          pass

      def _convert_data(
          self,
          vrs_writer: VRSWriter,
          rosbag_reader: RosbagReader,
      ) -> None:
          """Convert and write data records."""
          # 実装: 時系列順にメッセージを読み込み、VRSに書き込み
          pass

      def _convert_image_message(self, msg_data: dict) -> bytes:
          """Convert ROS Image message to VRS format."""
          # 実装
          pass

      def _convert_imu_message(self, msg_data: dict) -> dict[str, Any]:
          """Convert ROS Imu message to VRS format."""
          # 実装
          pass
  ```

- [ ] 🔎 **確認**: テストが成功すること (GREEN)
  ```bash
  uv run pytest tests/test_rosbag_to_vrs_converter.py -v --cov=scripts/rosbag_to_vrs_converter
  ```

- [ ] 🧪 **テスト**: GREEN状態の確認

- [ ] 🛠 **エラー時対処**:
  - 変換に時間がかかる: タイムアウト設定を調整 (`@pytest.mark.timeout(300)` 等)
  - メモリ不足: ストリーミング処理に変更（一度に全データを読み込まない）

#### 手順 4.4: CLIスクリプト作成

- [ ] 🖐 **操作**: `convert_rosbag_to_vrs.py` を作成
  ```python
  #!/usr/bin/env python3
  """Convert RealSense ROSbag files to VRS format.

  Usage:
      python convert_rosbag_to_vrs.py input.bag output.vrs
      python convert_rosbag_to_vrs.py input.bag output.vrs --topics rgb depth accel gyro
  """

  import argparse
  import sys
  from pathlib import Path

  from scripts.rosbag_to_vrs_converter import RosbagToVRSConverter

  # デフォルトトピックマッピング
  DEFAULT_TOPIC_MAPPING = {
      "/device_0/sensor_1/Color_0/image/data": {"stream_id": 1001, "type": "rgb"},
      "/device_0/sensor_0/Depth_0/image/data": {"stream_id": 1002, "type": "depth"},
      "/device_0/sensor_2/Accel_0/imu/data": {"stream_id": 2001, "type": "imu_accel"},
      "/device_0/sensor_2/Gyro_0/imu/data": {"stream_id": 2002, "type": "imu_gyro"},
  }

  def main() -> int:
      """Main entry point."""
      parser = argparse.ArgumentParser(
          description="Convert RealSense ROSbag to VRS format",
          formatter_class=argparse.RawDescriptionHelpFormatter,
      )

      parser.add_argument("input", type=Path, help="Input ROSbag file")
      parser.add_argument("output", type=Path, help="Output VRS file")
      parser.add_argument(
          "--topics",
          nargs="+",
          choices=["rgb", "depth", "ir", "accel", "gyro"],
          help="Sensor types to include (default: all)",
      )
      parser.add_argument(
          "--verbose", "-v", action="store_true", help="Verbose output"
      )

      args = parser.parse_args()

      # 入力検証
      if not args.input.exists():
          print(f"Error: Input file not found: {args.input}", file=sys.stderr)
          return 1

      # トピックマッピングのフィルタリング
      topic_mapping = DEFAULT_TOPIC_MAPPING
      if args.topics:
          # フィルタリング実装
          pass

      if args.verbose:
          print(f"Converting: {args.input} -> {args.output}")
          print(f"Topics: {len(topic_mapping)}")

      # 変換実行
      try:
          converter = RosbagToVRSConverter(args.input, args.output, topic_mapping)
          converter.convert()

          if args.verbose:
              print(f"Conversion complete: {args.output}")
              print(f"File size: {args.output.stat().st_size / 1024 / 1024:.2f} MB")

          return 0

      except Exception as e:
          print(f"Error: {e}", file=sys.stderr)
          if args.verbose:
              import traceback
              traceback.print_exc()
          return 1

  if __name__ == "__main__":
      sys.exit(main())
  ```

- [ ] 🔎 **確認**: CLIスクリプトが動作すること
  ```bash
  uv run python convert_rosbag_to_vrs.py --help
  ```
  **期待結果:** ヘルプメッセージが表示される

- [ ] 🧪 **テスト**: 実際の変換テスト
  ```bash
  uv run python convert_rosbag_to_vrs.py \
    data/rosbag/d435i_walk_around.bag \
    data/vrs/d435i_walk_around.vrs \
    --verbose
  ```
  **期待:** VRSファイルが作成され、エラーなく完了

- [ ] 🛠 **エラー時対処**:
  - `FileNotFoundError`: 出力ディレクトリを作成 (`mkdir -p data/vrs`)
  - 変換エラー: `--verbose`フラグでスタックトレースを確認

---

### フェーズ 5: VRS Inspector/Playerスクリプト実装 (見積: 2.5h)

このフェーズでは、VRSファイルの内容を確認・再生するスクリプトを実装します。

#### 手順 5.1: VRS Inspectorスクリプト作成 (TDD)

- [ ] 🖐 **操作**: `tests/test_inspect_vrs.py` を作成（統合テスト）
  ```python
  # tests/test_inspect_vrs.py
  import pytest
  from pathlib import Path
  import subprocess

  @pytest.fixture
  def sample_vrs_file(tmp_path):
      """テスト用VRSファイルを作成"""
      # VRSファイル作成ロジック
      pass

  def test_inspect_vrs_basic(sample_vrs_file):
      """inspect_vrs.pyが基本情報を表示できること"""
      result = subprocess.run(
          ["uv", "run", "python", "inspect_vrs.py", str(sample_vrs_file)],
          capture_output=True,
          text=True,
      )
      assert result.returncode == 0
      assert "Streams:" in result.stdout
      assert "Records:" in result.stdout
  ```

- [ ] 🔎 **確認**: テストが失敗すること (RED)

- [ ] 🧪 **テスト**: RED確認

- [ ] 🛠 **エラー時対処**: なし

#### 手順 5.2: VRS Inspector実装 (GREEN)

- [ ] 🖐 **操作**: `inspect_vrs.py` を作成
  ```python
  #!/usr/bin/env python3
  """Inspect VRS files and display metadata and statistics.

  Usage:
      python inspect_vrs.py file.vrs
      python inspect_vrs.py file.vrs --verbose
  """

  import argparse
  import sys
  from pathlib import Path

  from scripts.vrs_reader import VRSReader
  from scripts.timestamp_handler import format_timestamp_iso, ros_timestamp_to_datetime

  def main() -> int:
      """Main entry point."""
      parser = argparse.ArgumentParser(description="Inspect VRS files")
      parser.add_argument("vrsfile", type=Path, help="VRS file to inspect")
      parser.add_argument("--verbose", "-v", action="store_true")

      args = parser.parse_args()

      if not args.vrsfile.exists():
          print(f"Error: File not found: {args.vrsfile}", file=sys.stderr)
          return 1

      try:
          with VRSReader(args.vrsfile) as reader:
              print(f"VRS file: {args.vrsfile}")
              print(f"File size: {args.vrsfile.stat().st_size / 1024 / 1024:.2f} MB")
              print()

              stream_ids = reader.get_stream_ids()
              print(f"Streams: {len(stream_ids)}")

              for stream_id in stream_ids:
                  print(f"\nStream {stream_id}:")

                  # Configuration読み込み
                  try:
                      config = reader.read_configuration(stream_id)
                      print(f"  Configuration: {config}")
                  except Exception as e:
                      print(f"  Configuration: (error: {e})")

                  # Data records統計
                  records = list(reader.read_data_records(stream_id))
                  print(f"  Data records: {len(records)}")

                  if records:
                      timestamps = [r["timestamp"] for r in records]
                      print(f"  Time range: {min(timestamps):.3f}s - {max(timestamps):.3f}s")
                      print(f"  Duration: {max(timestamps) - min(timestamps):.3f}s")

                      if args.verbose and len(records) <= 10:
                          print("  Sample records:")
                          for r in records[:5]:
                              print(f"    [{r['timestamp']:.6f}s] {len(r.get('data', b''))} bytes")

          return 0

      except Exception as e:
          print(f"Error: {e}", file=sys.stderr)
          if args.verbose:
              import traceback
              traceback.print_exc()
          return 1

  if __name__ == "__main__":
      sys.exit(main())
  ```

- [ ] 🔎 **確認**: テストが成功すること (GREEN)
  ```bash
  uv run pytest tests/test_inspect_vrs.py -v
  ```

- [ ] 🧪 **テスト**: 実際のVRSファイルで動作確認
  ```bash
  uv run python inspect_vrs.py data/vrs/d435i_walk_around.vrs
  ```
  **期待:** ストリーム情報とレコード統計が表示される

- [ ] 🛠 **エラー時対処**:
  - `KeyError`: VRSReaderのデータ構造を確認・修正

#### 手順 5.3: VRS Playerスクリプト作成（オプション）

- [ ] 🖐 **操作**: `play_vrs.py` を作成（基本的な再生機能）
  ```python
  #!/usr/bin/env python3
  """Play VRS files and stream sensor data.

  Usage:
      python play_vrs.py file.vrs
      python play_vrs.py file.vrs --stream 1001 --limit 100
  """

  import argparse
  import sys
  from pathlib import Path

  from scripts.vrs_reader import VRSReader

  def main() -> int:
      """Main entry point."""
      parser = argparse.ArgumentParser(description="Play VRS files")
      parser.add_argument("vrsfile", type=Path, help="VRS file to play")
      parser.add_argument("--stream", type=int, help="Stream ID to play")
      parser.add_argument("--limit", "-l", type=int, help="Limit records")
      parser.add_argument("--format", choices=["human", "csv", "json"], default="human")

      args = parser.parse_args()

      if not args.vrsfile.exists():
          print(f"Error: File not found: {args.vrsfile}", file=sys.stderr)
          return 1

      try:
          with VRSReader(args.vrsfile) as reader:
              stream_ids = reader.get_stream_ids()

              if args.stream:
                  if args.stream not in stream_ids:
                      print(f"Error: Stream {args.stream} not found", file=sys.stderr)
                      return 1
                  stream_ids = [args.stream]

              for stream_id in stream_ids:
                  records = list(reader.read_data_records(stream_id))

                  if args.limit:
                      records = records[:args.limit]

                  for record in records:
                      if args.format == "human":
                          print(f"[{record['timestamp']:10.6f}s] Stream {stream_id}: {len(record.get('data', b''))} bytes")
                      elif args.format == "csv":
                          print(f"{record['timestamp']:.6f},{stream_id},{len(record.get('data', b''))}")
                      # JSON実装は省略

          return 0

      except Exception as e:
          print(f"Error: {e}", file=sys.stderr)
          return 1

  if __name__ == "__main__":
      sys.exit(main())
  ```

- [ ] 🔎 **確認**: Playerスクリプトが動作すること
  ```bash
  uv run python play_vrs.py data/vrs/d435i_walk_around.vrs --limit 10
  ```

- [ ] 🧪 **テスト**: 統合テスト実行

- [ ] 🛠 **エラー時対処**: inspect_vrs.pyと同様

---

### フェーズ 6: 統合テストと検証 (見積: 2.5h)

このフェーズでは、全体のワークフローが正しく動作することを検証します。

#### 手順 6.1: エンドツーエンド統合テスト作成

- [ ] 🖐 **操作**: `tests/test_integration_rosbag_to_vrs.py` を作成
  ```python
  # tests/test_integration_rosbag_to_vrs.py
  """Integration tests for complete ROSbag to VRS workflow."""

  import pytest
  from pathlib import Path
  import subprocess

  @pytest.mark.integration
  def test_full_conversion_workflow(tmp_path, data_dir):
      """完全な変換ワークフローのテスト"""
      rosbag_file = data_dir / "rosbag" / "d435i_walk_around.bag"
      vrs_file = tmp_path / "output.vrs"

      # 1. ROSbag to VRS変換
      result = subprocess.run(
          [
              "uv", "run", "python", "convert_rosbag_to_vrs.py",
              str(rosbag_file),
              str(vrs_file),
              "--verbose"
          ],
          capture_output=True,
          text=True,
      )

      assert result.returncode == 0, f"Conversion failed: {result.stderr}"
      assert vrs_file.exists(), "VRS file was not created"
      assert vrs_file.stat().st_size > 0, "VRS file is empty"

      # 2. VRS inspect実行
      result = subprocess.run(
          ["uv", "run", "python", "inspect_vrs.py", str(vrs_file)],
          capture_output=True,
          text=True,
      )

      assert result.returncode == 0, f"Inspect failed: {result.stderr}"
      assert "Streams:" in result.stdout
      assert "1001" in result.stdout  # RGB stream
      assert "1002" in result.stdout  # Depth stream

      # 3. VRS play実行
      result = subprocess.run(
          [
              "uv", "run", "python", "play_vrs.py",
              str(vrs_file),
              "--limit", "10"
          ],
          capture_output=True,
          text=True,
      )

      assert result.returncode == 0, f"Play failed: {result.stderr}"

  @pytest.mark.integration
  def test_data_integrity(tmp_path, data_dir):
      """データ整合性のテスト"""
      from scripts.rosbag_reader import RosbagReader
      from scripts.vrs_reader import VRSReader
      from scripts.rosbag_to_vrs_converter import RosbagToVRSConverter

      rosbag_file = data_dir / "rosbag" / "d435i_walk_around.bag"
      vrs_file = tmp_path / "output.vrs"

      topic_mapping = {
          "/device_0/sensor_1/Color_0/image/data": {"stream_id": 1001, "type": "rgb"},
      }

      # 変換
      converter = RosbagToVRSConverter(rosbag_file, vrs_file, topic_mapping)
      converter.convert()

      # メッセージ数の比較
      with RosbagReader(rosbag_file) as rosbag:
          rosbag_messages = list(rosbag.read_messages("/device_0/sensor_1/Color_0/image/data"))

      with VRSReader(vrs_file) as vrs:
          vrs_records = list(vrs.read_data_records(1001))

      assert len(vrs_records) == len(rosbag_messages), \
          f"Record count mismatch: VRS={len(vrs_records)}, ROSbag={len(rosbag_messages)}"
  ```

- [ ] 🔎 **確認**: 統合テストが実行できること
  ```bash
  uv run pytest tests/test_integration_rosbag_to_vrs.py -v -m integration
  ```
  **期待:** 全テストPASS

- [ ] 🧪 **テスト**: 統合テスト結果の確認

- [ ] 🛠 **エラー時対処**:
  - タイムアウト: `@pytest.mark.timeout(600)` を追加
  - データ不整合: デバッグ出力を追加して原因特定

#### 手順 6.2: パフォーマンス測定

- [ ] 🖐 **操作**: 変換時間とファイルサイズの測定
  ```bash
  # 変換時間測定
  time uv run python convert_rosbag_to_vrs.py \
    data/rosbag/d435i_walk_around.bag \
    data/vrs/d435i_walk_around.vrs \
    --verbose

  # ファイルサイズ比較
  ls -lh data/rosbag/d435i_walk_around.bag
  ls -lh data/vrs/d435i_walk_around.vrs
  ```

- [ ] 🔎 **確認**: 性能指標を記録
  ```markdown
  # パフォーマンス測定結果

  - ROSbagサイズ: [XXX] MB
  - VRSサイズ: [XXX] MB
  - 圧縮率: [XX]%
  - 変換時間: [XX]秒
  - 処理速度: [XX] MB/s
  ```
  **結果を `docs/performance_results.md` に記録**

- [ ] 🧪 **テスト**: 性能基準の確認
  - 変換時間が妥当な範囲内であること（目安: 1GB/分以上）
  - VRSファイルサイズがROSbagと同等以下であること

- [ ] 🛠 **エラー時対処**:
  - 変換が遅い: プロファイリングツール（cProfile）で ボトルネック特定
  - ファイルサイズが大きい: VRS圧縮設定を確認・調整

#### 手順 6.3: 全テストスイート実行

- [ ] 🖐 **操作**: 全テストを実行してカバレッジレポート生成
  ```bash
  uv run pytest tests/ -v --cov=scripts --cov-report=html --cov-report=term-missing
  ```

- [ ] 🔎 **確認**: 全テストPASS、カバレッジ80%以上
  ```bash
  open htmlcov/index.html  # ブラウザでカバレッジレポート確認
  ```
  **期待結果:**
  ```
  ================================ test session starts =================================
  ...
  tests/test_vrs_writer.py::test_vrs_writer_initialization PASSED
  ...
  ================================ XX passed in X.XXs ==================================

  ----------- coverage: platform linux, python 3.x.x -----------
  Name                                 Stmts   Miss  Cover   Missing
  ------------------------------------------------------------------
  scripts/vrs_writer.py                  45      2    96%   12, 34
  scripts/vrs_reader.py                  38      1    97%   56
  scripts/rosbag_to_vrs_converter.py     89      8    91%   ...
  ------------------------------------------------------------------
  TOTAL                                 345     23    93%
  ```

- [ ] 🧪 **テスト**: カバレッジ不足箇所の特定と追加テスト作成

- [ ] 🛠 **エラー時対処**:
  - テスト失敗: 失敗したテストを個別に実行して原因特定
  - カバレッジ不足: 未テストのブランチを特定し、テストケース追加

#### 手順 6.4: ドキュメント最終更新

- [ ] 🖐 **操作**: README.mdにVRS変換機能を追加
  ```markdown
  ## VRS Conversion

  Convert ROSbag files to VRS format for AR/VR applications.

  ### Convert ROSbag to VRS

  ```bash
  # Basic conversion
  uv run python convert_rosbag_to_vrs.py input.bag output.vrs

  # Convert specific sensors only
  uv run python convert_rosbag_to_vrs.py input.bag output.vrs --topics rgb depth

  # Verbose mode
  uv run python convert_rosbag_to_vrs.py input.bag output.vrs --verbose
  ```

  ### Inspect VRS files

  ```bash
  # Show VRS file information
  uv run python inspect_vrs.py output.vrs

  # Verbose mode with detailed statistics
  uv run python inspect_vrs.py output.vrs --verbose
  ```

  ### Play VRS files

  ```bash
  # Stream all data
  uv run python play_vrs.py output.vrs

  # Stream specific stream with limit
  uv run python play_vrs.py output.vrs --stream 1001 --limit 100
  ```
  ```

- [ ] 🔎 **確認**: README.mdが更新されていること
  ```bash
  grep "VRS Conversion" README.md
  ```

- [ ] 🧪 **テスト**: ドキュメントの例が実際に動作すること

- [ ] 🛠 **エラー時対処**: なし

#### 手順 6.5: Justfileの作成（オプション）

- [ ] 🖐 **操作**: `justfile` を作成（よく使うコマンドをまとめる）
  ```makefile
  # justfile

  # Show available commands
  default:
      @just --list

  # Install dependencies
  install:
      uv pip install -e .

  # Run all tests
  test:
      uv run pytest tests/ -v

  # Run tests with coverage
  test-cov:
      uv run pytest tests/ -v --cov=scripts --cov-report=html --cov-report=term-missing

  # Run integration tests only
  test-integration:
      uv run pytest tests/ -v -m integration

  # Type check
  typecheck:
      uv run mypy scripts/ --strict

  # Lint
  lint:
      uv run ruff check scripts/ tests/

  # Format
  format:
      uv run ruff format scripts/ tests/

  # Convert sample ROSbag to VRS
  convert-sample:
      uv run python convert_rosbag_to_vrs.py \
        data/rosbag/d435i_walk_around.bag \
        data/vrs/d435i_walk_around.vrs \
        --verbose

  # Inspect sample VRS
  inspect-sample:
      uv run python inspect_vrs.py data/vrs/d435i_walk_around.vrs

  # Clean generated files
  clean:
      rm -rf data/vrs/*.vrs
      rm -rf htmlcov/
      rm -rf .pytest_cache/
      rm -rf .coverage
  ```

- [ ] 🔎 **確認**: justコマンドが動作すること
  ```bash
  just --list
  just test
  just convert-sample
  ```

- [ ] 🧪 **テスト**: 各justコマンドが正しく動作すること

- [ ] 🛠 **エラー時対処**:
  - `just: command not found`: `cargo install just` または `brew install just`

---

## 4. 作業チェックリスト

*作業が完了したら `[ ]` を `[x]` に変更します。*

### フェーズ 1: 環境構築と調査
- [x] 手順1.1: PyVRSインストールとバージョン確認
- [x] 手順1.2: PyVRS APIドキュメント調査とモジュール構造把握
- [ ] 手順1.3: 最小限のVRSファイル作成テスト
- [ ] 手順1.4: VRSファイル読み込みテスト
- [ ] 手順1.5: ROSbag → VRS データマッピング仕様書の作成

### フェーズ 2: VRS Writerモジュール実装 (TDD)
- [ ] 手順2.1: VRS Writerモジュールのインターフェース設計
- [ ] 手順2.2: VRS Writerテストケース作成 (RED)
- [ ] 手順2.3: VRS Writer実装 (GREEN)
- [ ] 手順2.4: VRS Writerリファクタリング (REFACTOR)

### フェーズ 3: VRS Readerモジュール実装 (TDD)
- [ ] 手順3.1: VRS Readerテストケース作成 (RED)
- [ ] 手順3.2: VRS Reader実装 (GREEN)
- [ ] 手順3.3: VRS Readerリファクタリング (REFACTOR)

### フェーズ 4: ROSbag to VRS 変換スクリプト実装 (TDD)
- [ ] 手順4.1: 変換ロジックモジュール設計
- [ ] 手順4.2: Converterテストケース作成 (RED)
- [ ] 手順4.3: Converter実装 (GREEN)
- [ ] 手順4.4: CLIスクリプト作成

### フェーズ 5: VRS Inspector/Playerスクリプト実装
- [ ] 手順5.1: VRS Inspectorスクリプト作成 (TDD)
- [ ] 手順5.2: VRS Inspector実装 (GREEN)
- [ ] 手順5.3: VRS Playerスクリプト作成（オプション）

### フェーズ 6: 統合テストと検証
- [ ] 手順6.1: エンドツーエンド統合テスト作成
- [ ] 手順6.2: パフォーマンス測定
- [ ] 手順6.3: 全テストスイート実行
- [ ] 手順6.4: ドキュメント最終更新
- [ ] 手順6.5: Justfileの作成（オプション）

---

## 5. 作業に使用するコマンド参考情報

### 基本的な開発ワークフロー

```bash
# 依存関係のインストール
uv pip install vrs numpy opencv-python rosbags pytest pytest-cov mypy ruff

# 開発環境確認
uv run python --version
uv run python -c "import vrs; print('PyVRS OK')"

# プロジェクトルートに移動
cd /home/user/realsense_vrs_sandbox
```

### テストと品質管理

```bash
# 全テストの実行
uv run pytest tests/ -v

# カバレッジ付きテスト
uv run pytest tests/ -v --cov=scripts --cov-report=html --cov-report=term-missing

# 統合テストのみ実行
uv run pytest tests/ -v -m integration

# 特定のテストファイルのみ実行
uv run pytest tests/test_vrs_writer.py -v

# 型チェック
uv run mypy scripts/ --strict

# リンター
uv run ruff check scripts/ tests/

# フォーマット
uv run ruff format scripts/ tests/
```

### VRS関連の実行例

```bash
# VRSファイル作成テスト
uv run python scripts/create_sample_vrs.py

# VRSファイル読み込みテスト
uv run python scripts/read_sample_vrs.py data/test_sample.vrs

# ROSbag to VRS変換
uv run python convert_rosbag_to_vrs.py \
  data/rosbag/d435i_walk_around.bag \
  data/vrs/d435i_walk_around.vrs \
  --verbose

# VRSファイルのインスペクト
uv run python inspect_vrs.py data/vrs/d435i_walk_around.vrs

# VRSファイルの再生
uv run python play_vrs.py data/vrs/d435i_walk_around.vrs --limit 100
```

### デバッグ用コマンド

```bash
# PyVRS APIの調査
uv run python -c "import vrs; print(dir(vrs))"
uv run python -c "import vrs; help(vrs)"

# ROSbag情報確認
uv run python extract_realsense_data.py data/rosbag/d435i_walk_around.bag

# ファイルサイズ比較
ls -lh data/rosbag/d435i_walk_around.bag
ls -lh data/vrs/d435i_walk_around.vrs

# パフォーマンス測定
time uv run python convert_rosbag_to_vrs.py input.bag output.vrs
```

### Git操作

```bash
# 変更内容の確認
git status
git diff

# コミット（端的なメッセージ）
git add <files>
git commit -m "Implement VRS writer module"

# 詳細はgit noteに記録
git notes add -m "詳細な実装内容や変更理由をここに記述"

# プッシュ
git push -u origin <branch-name>
```

---

## 6. 完了の定義

*作業が最後まで完了したら `[ ]` を `[x]` にしつつ、作業が本当に完了したかをチェックします*

- [ ] **機能完全性**: ROSbag to VRS変換が全センサータイプ（RGB, Depth, Accel, Gyro）で正常に動作すること
- [ ] **テストカバレッジ**: 全モジュールのテストカバレッジが80%以上であること
- [ ] **統合テスト**: エンドツーエンド統合テストが全てPASSすること
- [ ] **データ整合性**: 変換後のVRSファイルが元のROSbagと同じレコード数を持つこと
- [ ] **パフォーマンス**: 変換速度が1GB/分以上であること（目安）
- [ ] **ドキュメント**: README.md、仕様書、設計書が全て最新状態であること
- [ ] **コード品質**: mypy strict、ruffチェックが全てPASSすること
- [ ] **ユーザビリティ**: CLIスクリプトが--helpで明確な使用方法を提供すること
- [ ] **再現性**: justコマンドまたはドキュメント記載の手順で誰でも同じ結果を得られること
- [ ] **エラーハンドリング**: 想定されるエラー（ファイル未存在、権限不足等）に対して適切なエラーメッセージを表示すること

---

## 7. 作業記録

**重要な注意事項：**

*   作業開始前に必ず `date "+%Y-%m-%d %H:%M:%S %Z%z"` コマンドで現在時刻を確認し、正確な日時を記録します。
*   各作業項目を開始する際と完了する際の両方で記録を行うこと。
*   作業内容は具体的なコマンドや操作手順を詳細に記載すること。
*   結果・備考欄には成功／失敗、エラー内容、解決方法、重要な気づきを必ず記入すること。
*   複数のフェーズがある場合は、フェーズごとに開始・完了の記録を取ること。
*   コード変更を行った場合は、変更したファイル名と変更内容の概要を記録すること。
*   エラーが発生した場合は、エラーメッセージと解決策を詳細に記録すること。

| 日付 | 時刻 | 作業者 | 作業内容 | 結果・備考 |
| :--- | :--- | :--- | :--- | :--- |
| 2025-11-19 | 03:37:04 UTC+0000 | Claude (Sonnet 4.5) | フェーズ1 手順1.1開始: PyVRSインストール | uv add vrsでvrs 1.2.1をインストール成功 |
| 2025-11-19 | 03:37:04 UTC+0000 | Claude (Sonnet 4.5) | PyVRSバージョン確認とモジュール名調査 | 重要な発見: モジュール名は`vrs`ではなく`pyvrs`。`import pyvrs`でインポート成功 |
| 2025-11-19 | 03:37:04 UTC+0000 | Claude (Sonnet 4.5) | tests/test_vrs_import.py作成とテスト実行 | テスト2件作成、全てPASS。手順1.1完了 |
| 2025-11-19 | 03:40:25 UTC+0000 | Claude (Sonnet 4.5) | 手順1.2開始: PyVRS API調査 | scripts/investigate_pyvrs_api.py作成、docs/pyvrs_api_investigation.md生成 |
| 2025-11-19 | 03:43:56 UTC+0000 | Claude (Sonnet 4.5) | **重大な発見: PyVRSは読み取り専用** | PyVRSにはWriterクラスが存在しない。VRS C++ライブラリにはRecordFileWriterがあるが、Pythonバインディングに公開されていない。Option 1-3の対処法を提案。作業計画の大幅な見直しが必要。 |
| | | | | |
| | | | | |
| | | | | |
| | | | | |
| | | | | |
| | | | | |
| | | | | |

---

## 8. 補足資料

### 参考リンク

- **VRS公式ドキュメント**: https://facebookresearch.github.io/vrs/
- **PyVRS GitHubリポジトリ**: https://github.com/facebookresearch/pyvrs
- **PyVRS API Documentation**: https://pyvrs.readthedocs.io/en/latest/
- **VRS C++ API**: https://facebookresearch.github.io/vrs/doxygen/
- **ROSbags Library**: https://pypi.org/project/rosbags/
- **Project Aria**: https://projectaria.com/ (VRS使用事例)

### 用語集

- **VRS (Virtual Reality Stream)**: Meta社が開発したマルチストリームセンサーデータフォーマット
- **Stream**: VRSファイル内の独立したセンサーデータ系列（例: RGB Camera Stream）
- **Record**: ストリーム内の単一のデータポイント（Configuration/State/Data）
- **Content Block**: レコード内のデータブロック（Metadata/Image/Audio等）
- **DataLayout**: VRS内のデータ構造定義
- **ROSbag**: ROS (Robot Operating System) のデータ記録フォーマット
- **TDD (Test-Driven Development)**: テスト駆動開発手法（RED-GREEN-REFACTOR）

### トラブルシューティング

#### PyVRSインストール失敗

**症状:** `pip install vrs` が失敗する

**原因と対処:**
1. Windowsの場合: ソースビルドが必要
   ```bash
   git clone --recursive https://github.com/facebookresearch/pyvrs.git
   cd pyvrs
   git submodule update --init --recursive
   python -m pip install -e .
   ```

2. システムライブラリ不足 (Linux):
   ```bash
   sudo apt-get update
   sudo apt-get install -y build-essential cmake liblz4-dev libzstd-dev libboost-all-dev
   ```

3. Python バージョン: Python 3.9+ が必須
   ```bash
   python --version  # 3.9以上を確認
   ```

#### VRSファイルが作成されない

**症状:** VRSWriterで書き込んだはずがファイルが0バイトまたは存在しない

**原因と対処:**
- `close()`メソッドを呼び出していない: コンテキストマネージャ（`with`文）を使用するか、明示的に`close()`を呼ぶ
- 書き込み権限がない: `chmod 755 data/` で権限を付与
- ディスク容量不足: `df -h` で確認

#### テストが遅い

**症状:** 統合テストに数分かかる

**対処:**
- 統合テストをマーク分け: `@pytest.mark.integration` を使用し、通常は `pytest tests/ -v -m "not integration"` で除外
- タイムアウト設定: `@pytest.mark.timeout(600)` で長時間テストに対応
- 並列実行: `pytest-xdist` を使用 (`pytest -n auto`)

#### 型チェックエラー

**症状:** `mypy --strict` で大量のエラー

**対処:**
- 段階的導入: まず `mypy scripts/` (non-strict) から始める
- `# type: ignore` コメントで一時的に抑制（非推奨、最小限に）
- PyVRS型スタブ不足: `py.typed` ファイルがない場合は `# type: ignore` で対応

---

## 9. 今後の拡張案

本作業計画書の範囲外ですが、将来的に検討できる拡張機能：

1. **画像圧縮オプション**
   - JPEG/PNG圧縮をサポートしてファイルサイズ削減
   - 圧縮品質の指定オプション追加

2. **IR (Infrared) センサー対応**
   - RealSense IRトピックが存在する場合のマッピング追加

3. **カメラキャリブレーション情報の埋め込み**
   - カメラ内部パラメータ、歪み係数をConfigurationレコードに含める

4. **時刻フィルタリング**
   - ROSbagの特定時間範囲のみをVRSに変換するオプション

5. **VRSからROSbagへの逆変換**
   - VRS → ROSbag変換機能の実装

6. **GUIツール**
   - VRSファイルのビジュアル再生・編集ツール（PyQt/Tkinter）

7. **Project Ariaデータセット対応**
   - Aria Glassesのデータフォーマットとの互換性確保

8. **ストリーミング変換**
   - リアルタイムでROStopicをVRSに記録

---

**作業計画書作成日:** 2025-11-19
**最終更新日:** 2025-11-19
**バージョン:** 1.0
