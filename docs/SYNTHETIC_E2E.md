# 人工 ROSbag と一連の変換テスト

**更新日: 2026-10-30**

このテストは、人工のセンサーデータから **実際の ROS1 bag を生成し、通常の変換コマンドで VRS に変換し、公式 PyVRS リーダーで読み戻す**ことを確認します。実収録ファイル、接続されたカメラ、代替のリーダー／ライターは使用しません。

- 生成器: [scripts/synthetic_rosbag.py](../scripts/synthetic_rosbag.py)
- 一連の変換テスト: [tests/test_synthetic_e2e.py](../tests/test_synthetic_e2e.py)
- 保存規約: [IMPLEMENTATION.md](IMPLEMENTATION.md)
- API の使用例: [VRS_API_CHEATSHEET.md](VRS_API_CHEATSHEET.md)

## 1. 手元で再現する

リポジトリのルートで実行してください。

```bash
uv sync --locked --group dev

VRS_E2E_DIR=$(mktemp -d)
uv run python -m scripts.synthetic_rosbag "$VRS_E2E_DIR/synthetic.bag" --frames 12
uv run python convert_to_vrs.py "$VRS_E2E_DIR/synthetic.bag" "$VRS_E2E_DIR/synthetic.vrs" --imu --compression zstd
uv run python inspect_vrs.py "$VRS_E2E_DIR/synthetic.vrs" --verbose
```

この指定では、入力 bag に静的な情報18件とデータ48件が入ります。出力は RGB・深度・加速度・角速度が各12件、合計48 Data レコードです。11ストリームそれぞれに Configuration があり、Transform・Device・Sensor・Options の7ストリームには Data レコードを作りません。

生成した `.bag`／`.vrs` は一時ディレクトリだけに保存されます。このリポジトリの `.gitignore` でも両拡張子を除外しています。コミットするものは生成器、テスト、仕様です。

### 自動検証

```bash
# 人工 bag の生成・実変換・公式リーダーによる比較
uv run pytest -q -m e2e

# ライターの境界条件や旧形式を含む、実収録不要の全回帰
uv run pytest -q -m "not integration"
```

`e2e` は `integration` と別の区分です。`integration` は利用者が指定した実収録 bag を使用するテストで、人工データによる通常回帰に必要ありません。

## 2. 生成データの仕様

### 生成器の既定値

| 項目 | 既定値 |
|---|---|
| 画像 | 640×480、RGB8 と 16UC1 |
| フレーム数 | RGB・深度それぞれ4 |
| IMU | 加速度・角速度それぞれ4 |
| 開始時刻 | 10秒 |
| フレーム間隔 | 40,000,000 ns、25 Hz |
| RGB・深度の時刻 | フレームごとに同一 |
| 加速度の時刻 | そのフレームの時刻 +1 ms |
| 角速度の時刻 | そのフレームの時刻 +2 ms |
| 静的情報の時刻 | 最初のフレームより1 ms前 |
| 深度倍率 | 0.002 m/unit |
| 行余白 | 0バイト |
| 深度のバイト順 | リトルエンディアン |

値は座標とフレーム番号から決定するため、乱数種や外部データに依存しません。フレーム番号を `i`、画素座標を `x, y` とすると、RGB は次の値です。

| 成分 | 値 |
|---|---|
| R | `(x + 7*i) % 256` |
| G | `(y + 11*i) % 256` |
| B | `(x + y + 13*i) % 256` |
| 深度 | `(31*x + 17*y + 101*i) % 65536` |
| 加速度 | `(0.25+i, -0.5-i, 9.75+0.125*i)` |
| 角速度 | `(0.125+i, -0.25-i, 0.5*i)` |

既定寸法では、深度の左上を0、右下を65535に設定し、無効深度と最大値も含めます。

CameraInfo は非自明な K・D と R・P を持ちます。Depth の並進は `(0.002, -0.003, 0.004)`、Color の並進は `(0.025, -0.005, 0.002)`、Color の回転は `(0, 0, 0.6, 0.8)` です。デバイス名や製造番号も人工の文字列で、実機由来の情報ではありません。

StreamInfo の型定義は bag 内に埋め込み、`AnyReader` で独立に復号できるようにしています。Options には Exposure と Depth Units を含め、変換器が深度倍率を固定値で済ませていないことも検証します。

### 生成オプション

| CLI オプション | 意味 |
|---|---|
| `--width`、`--height` | 画像の幅と高さ |
| `--frames` | 各データストリームの件数 |
| `--frame-period-ns` | フレーム周期。IMU の +2 ms より長くする必要があります |
| `--depth-scale` | Options に記録する深度倍率 |
| `--row-padding-bytes` | 各画像行の末尾に追加する余白 |
| `--depth-bigendian` | 深度画像をビッグエンディアンで格納 |

生成器は既存ファイルへの上書きと、不正な寸法・件数・周期・深度倍率を拒否します。フレームを順に生成するため、記録を長くしても全フレームをメモリに保持しません。

API を使う場合は、次のように小さな本物の bag を作成できます。

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.synthetic_rosbag import SyntheticBagSpec, write_synthetic_rosbag

with TemporaryDirectory(prefix="synthetic-bag-") as directory:
    path = write_synthetic_rosbag(
        Path(directory) / "small.bag",
        SyntheticBagSpec(width=8, height=6, frame_count=2),
    )
    assert path.is_file()
```

`SyntheticBagSpec` では、CLI の項目に加えて `start_time_ns` も指定できます。

## 3. E2E の合格条件

主テストは640×480×12フレームで、`none`・`lz4`・`zstd` を個別に実行します。RGB-D のペイロードは約18.4 MBとなり、既定の16 MiB書き出し閾値を超えます。書き出し後の末尾まで検査することで、途中の書き出しによる欠落を検出します。

| 検査対象 | 合格条件 |
|---|---|
| 入力 | ROS1 bag の実ファイルで、標準 `AnyReader` が復号できます |
| 実行経路 | `convert_to_vrs.py --imu --compression ...` を別プロセスで実行し、終了コードが0です |
| 保存形式 | バージョン2と画像／IMUの符号化タグが一致します |
| RGB | 全12枚が `(480, 640, 3)`・uint8で、入力と全画素一致します |
| 深度 | 全12枚が `(480, 640)`・uint16で、入力と全画素一致します |
| IMU | 画像ブロックを持たず、`doubles` の全3成分が入力と一致します |
| 時刻 | 全レコードで bag の時刻と対応し、全体の順序が非減少です |
| 件数 | RGB・深度・加速度・角速度が各12件あり、設定のみのストリームには Data がありません |
| カメラ | 寸法、符号化、frame_id、歪みモデル、K・D・R・P、fpsが一致します |
| IMU 設定 | 種別、単位、frame_id、fps／sample_rateが入力に一致します |
| 周辺情報 | 外部パラメータ、デバイス情報、センサー名、Optionsと深度倍率が一致します |

期待値は入力 bag を `AnyReader.deserialize()` で読み、変換器の内部関数から独立に作成します。出力側も `scripts.vrs_reader.VRSReader` を使わず、**公式 `pyvrs.SyncVRSReader`** を直接使用します。

深度の表示向け変換を避けるため、公式リーダーに `ImageConversion.OFF` を指定します。画像・IMUはハッシュだけで判定せず、配列の全要素を比較します。人工データの時刻比較は相対誤差0、絶対誤差1 nsです。エポック時刻などの浮動小数精度は、ライターの境界条件テストで別に扱います。

さらに、8×6の小さな bag を生成 CLI から作成し、各行に4バイトの余白を加え、深度をビッグエンディアンにした場合も一連の変換を検査します。生成器自身の既知画素、深度の端値、不正入力、上書き拒否も確認します。

## 4. 他のテストとの関係

| テスト | 対象 |
|---|---|
| `test_synthetic_e2e.py` | 本物の bag と VRS、通常 CLI、独立した公式リーダー |
| `test_rosbag_to_vrs_converter.py` | 小さな本物の人工 bag と変換 API、統計・設定 |
| `test_converter_synthetic.py` | 代替実装を使う分岐・設定のみの処理 |
| `test_official_pyvrs_writer.py` | 公式バックエンド、画像・数値メタデータ、モジュール書き換えがないこと |
| `test_vrs_writer_lifecycle.py` | 書き出し境界、同時刻、最終レコード、不正入力、終了処理 |
| `test_vrs_reader_compatibility.py` | 旧1行 GREY8 形式を再生成した読み出し |
| `test_real_rosbag_integration.py` | 明示指定された外部の実収録 bag |

[CI 設定](../.github/workflows/tests.yml) は Python 3.10.6 と3.12で固定依存と通常回帰を実行します。この文書のテスト定義と、各 CI 実行の成功・失敗は区別してください。

## 5. このテストが保証しない範囲

人工 ROS1 bag の再現可能な範囲を確認するテストです。実機の全ファームウェア・全トピック構成、任意の ROS2 bag、Aria などの機器固有のデータ定義への対応を保証しません。

また、元の bag に含まれる全フィールドの保存を保証しません。赤外線画像、追加のフレームメタデータ、IMU の姿勢・共分散などは現行の保存対象外です。旧 CUSTOM ブロックを読む処理は保持しますが、過去のすべての実収録 VRS をこのテストで読み直しているわけではありません。

実収録データの取得・アップロードは行いません。手元の実収録 bag の検証は、利用者が `REALSENSE_ROSBAG_PATH` を明示する別のテストです。
