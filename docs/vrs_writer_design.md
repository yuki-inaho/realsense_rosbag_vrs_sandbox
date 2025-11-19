# VRS Writer モジュール設計

**作成日:** 2025-11-19
**バージョン:** 1.0

## 概要

`vrs_writer.py`は、pyvrs_writer C++バインディングをラップし、使いやすいPythonインターフェースを提供するモジュールです。このモジュールは、ROSbagからVRSへの変換において、VRSファイルの作成とデータ書き込みを担当します。

## アーキテクチャ

```
┌─────────────────────────────────────┐
│   scripts/vrs_writer.py             │
│   (Pythonラッパーモジュール)        │
│   - 高レベルAPI                      │
│   - 型変換・バリデーション          │
│   - エラーハンドリング              │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│   pyvrs_writer (C++ bindings)       │
│   - VRS C++ライブラリへの低レベル  │
│     バインディング                  │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│   VRS C++ Library                    │
│   - RecordFileWriter                 │
│   - ストリーム管理                  │
│   - レコード書き込み                │
└─────────────────────────────────────┘
```

## クラス: VRSWriter

### 責務

- VRSファイルの作成と管理
- ストリームの追加
- Configurationレコードの書き込み（JSON形式）
- Dataレコードの書き込み（タイムスタンプ付きバイナリデータ）
- ファイルのクローズとリソース管理
- エラーハンドリングとバリデーション
- Pythonic なインターフェース提供（コンテキストマネージャ対応）

### インターフェース

#### `__init__(self, filepath: Path | str)`

VRSファイルを作成・オープンします。

**パラメータ:**
- `filepath`: VRSファイルのパス（Path または str）

**例外:**
- `ValueError`: ファイルパスが無効な場合
- `RuntimeError`: VRSファイルの作成に失敗した場合

**使用例:**
```python
from pathlib import Path
from scripts.vrs_writer import VRSWriter

writer = VRSWriter(Path("output.vrs"))
# または
writer = VRSWriter("output.vrs")
```

#### `add_stream(self, stream_id: int, stream_name: str) -> None`

新しいストリームを追加します。

**パラメータ:**
- `stream_id`: ストリームID（正の整数、ユニーク）
- `stream_name`: ストリーム名（人間が読める名前）

**例外:**
- `ValueError`: stream_idが無効な場合（負の数、既存のIDと重複）
- `RuntimeError`: ストリーム追加に失敗した場合

**使用例:**
```python
writer.add_stream(1001, "RGB Camera")
writer.add_stream(1002, "Depth Camera")
writer.add_stream(2001, "IMU Accelerometer")
```

#### `write_configuration(self, stream_id: int, config_data: dict[str, Any]) -> None`

Configurationレコードを書き込みます。各ストリームにつき1回のみ呼び出し可能です。

**パラメータ:**
- `stream_id`: 対象ストリームのID
- `config_data`: 設定データ（JSON化可能な辞書）

**例外:**
- `ValueError`: stream_idが存在しない、またはconfig_dataがJSON化不可能
- `RuntimeError`: 書き込みに失敗した場合

**使用例:**
```python
rgb_config = {
    "sensor_type": "RGB Camera",
    "width": 640,
    "height": 480,
    "encoding": "rgb8",
    "frame_id": "camera_color_optical_frame"
}
writer.write_configuration(1001, rgb_config)
```

#### `write_data(self, stream_id: int, timestamp: float, data: bytes | list[int]) -> None`

Dataレコードを書き込みます。複数回呼び出し可能（時系列データ）。

**パラメータ:**
- `stream_id`: 対象ストリームのID
- `timestamp`: タイムスタンプ（秒、浮動小数点数、相対時刻）
- `data`: データペイロード
  - `bytes`: バイト列（画像データ等）
  - `list[int]`: 整数リスト（pyvrs_writer C++バインディングで使用）

**例外:**
- `ValueError`: stream_idが存在しない、timestampが負の値、dataが空
- `RuntimeError`: 書き込みに失敗した場合

**使用例:**
```python
# 画像データの書き込み（bytes）
image_bytes = b'\x00\x01\x02...'  # RGB画像データ
writer.write_data(1001, 0.0, list(image_bytes))

# IMUデータの書き込み（構造化データをJSONエンコード後にbytes化）
import json
imu_data = {"ax": 0.1, "ay": 0.2, "az": 9.8}
imu_bytes = json.dumps(imu_data).encode('utf-8')
writer.write_data(2001, 0.001, list(imu_bytes))
```

**重要な注意:**
- pyvrs_writer C++バインディングは `list[int]` を期待します
- `bytes` を渡す場合は `list(bytes_data)` で変換してください

#### `close(self) -> None`

VRSファイルをクローズします。ファイルを正常に終了するために必須です。

**例外:**
- `RuntimeError`: クローズに失敗した場合

**使用例:**
```python
writer.close()
```

#### コンテキストマネージャ対応

`__enter__` / `__exit__` を実装し、`with`文での使用をサポートします。

**使用例:**
```python
with VRSWriter("output.vrs") as writer:
    writer.add_stream(1001, "RGB Camera")
    writer.write_configuration(1001, {"width": 640, "height": 480})
    writer.write_data(1001, 0.0, [0x01, 0x02, 0x03])
# with ブロック終了時に自動的にclose()が呼ばれる
```

#### `is_open(self) -> bool`

VRSファイルが開いているかどうかを確認します。

**戻り値:**
- `True`: ファイルが開いている
- `False`: ファイルが閉じている

**使用例:**
```python
assert writer.is_open()
writer.close()
assert not writer.is_open()
```

## 完全な使用例

### 基本的な使用（コンテキストマネージャ）

```python
from pathlib import Path
from scripts.vrs_writer import VRSWriter

# VRSファイルを作成
with VRSWriter(Path("output.vrs")) as writer:
    # ストリームを追加
    writer.add_stream(1001, "RGB Camera")
    writer.add_stream(1002, "Depth Camera")
    writer.add_stream(2001, "IMU Accelerometer")

    # Configurationレコードを書き込み
    writer.write_configuration(1001, {
        "sensor_type": "RGB Camera",
        "width": 640,
        "height": 480,
        "encoding": "rgb8"
    })

    writer.write_configuration(1002, {
        "sensor_type": "Depth Camera",
        "width": 640,
        "height": 480,
        "encoding": "16UC1",
        "depth_scale": 0.001
    })

    writer.write_configuration(2001, {
        "sensor_type": "IMU Accelerometer",
        "unit": "m/s^2"
    })

    # データを書き込み
    rgb_data = b'\x00' * (640 * 480 * 3)  # ダミーRGB画像
    writer.write_data(1001, 0.0, list(rgb_data))
    writer.write_data(1001, 0.033, list(rgb_data))

    depth_data = b'\x00' * (640 * 480 * 2)  # ダミーDepth画像
    writer.write_data(1002, 0.0, list(depth_data))

    import json
    imu_data = json.dumps({"ax": 0.1, "ay": 0.2, "az": 9.8}).encode('utf-8')
    writer.write_data(2001, 0.0, list(imu_data))

# ファイルが自動的にクローズされる
```

### 手動クローズ（コンテキストマネージャ不使用）

```python
from scripts.vrs_writer import VRSWriter

writer = VRSWriter("output.vrs")
try:
    writer.add_stream(1001, "Test Stream")
    writer.write_configuration(1001, {"test": "config"})
    writer.write_data(1001, 0.0, [0x01, 0x02, 0x03])
finally:
    writer.close()
```

## エラーハンドリング

### 一般的なエラーケース

```python
from scripts.vrs_writer import VRSWriter

# 1. ストリームID重複
with VRSWriter("output.vrs") as writer:
    writer.add_stream(1001, "Stream 1")
    try:
        writer.add_stream(1001, "Stream 2")  # ValueError
    except ValueError as e:
        print(f"Error: {e}")

# 2. 存在しないストリームへの書き込み
with VRSWriter("output.vrs") as writer:
    writer.add_stream(1001, "Stream 1")
    try:
        writer.write_configuration(9999, {})  # ValueError
    except ValueError as e:
        print(f"Error: {e}")

# 3. タイムスタンプ逆行
with VRSWriter("output.vrs") as writer:
    writer.add_stream(1001, "Stream 1")
    writer.write_data(1001, 1.0, [0x01])
    try:
        writer.write_data(1001, 0.5, [0x02])  # ValueError (時刻逆行)
    except ValueError as e:
        print(f"Error: {e}")
```

## テスト戦略

### 単体テスト（pytest）

`tests/test_vrs_writer.py`で以下のケースをカバー:

1. **初期化テスト**
   - VRSWriterが正しく初期化される
   - ファイルが作成される

2. **コンテキストマネージャテスト**
   - `with`文で使用できる
   - 自動的にクローズされる

3. **ストリーム追加テスト**
   - ストリームが正しく追加される
   - 重複IDでエラーが発生する

4. **Configuration書き込みテスト**
   - JSON辞書が正しく書き込まれる
   - 無効なストリームIDでエラーが発生する

5. **Data書き込みテスト**
   - バイトデータが正しく書き込まれる
   - タイムスタンプが正しく処理される

6. **エラーハンドリングテスト**
   - 無効な入力で適切な例外が発生する

### 統合テスト

`tests/test_integration_vrs_writer.py`で以下をテスト:

- 大量データの書き込み（1000フレーム以上）
- 複数ストリーム同時書き込み
- 実際のVRSファイルがpyVRSで読み込み可能

## 実装上の注意事項

### DRY原則

- バリデーションロジックは共通化する
- pyvrs_writer C++バインディングへの呼び出しを抽象化する

### KISS原則

- インターフェースはシンプルに保つ
- 複雑な型変換は内部で処理

### SOLID原則

- **単一責任の原則**: VRSWriterはVRSファイル書き込みのみを担当
- **開放閉鎖の原則**: 新しいストリームタイプは継承なしで追加可能
- **依存性逆転の原則**: pyvrs_writerへの依存は抽象化

### 型ヒント

- すべてのメソッドに型ヒントを付ける
- `mypy --strict`でチェック可能にする

```python
from typing import Any
from pathlib import Path

class VRSWriter:
    def __init__(self, filepath: Path | str) -> None:
        ...

    def add_stream(self, stream_id: int, stream_name: str) -> None:
        ...

    def write_configuration(self, stream_id: int, config_data: dict[str, Any]) -> None:
        ...

    def write_data(self, stream_id: int, timestamp: float, data: bytes | list[int]) -> None:
        ...
```

## 依存関係

- **pyvrs_writer**: C++バインディング（Phase 1Aで実装済み）
- **json**: Configuration データのシリアライズ
- **pathlib**: ファイルパス処理

## パフォーマンス考慮事項

- **ストリーミング処理**: 大量データはメモリに展開せず、逐次書き込み
- **バッファリング**: VRS C++ライブラリのバッファリングを活用
- **型変換コスト**: `bytes` → `list[int]` 変換は最小限に

## 将来の拡張

- **圧縮オプション**: JPEG/PNG圧縮のサポート
- **非同期書き込み**: `asyncio`対応
- **進捗表示**: `tqdm`統合
- **メタデータ埋め込み**: カメラキャリブレーション情報

---

**変更履歴:**
- 2025-11-19: 初版作成
