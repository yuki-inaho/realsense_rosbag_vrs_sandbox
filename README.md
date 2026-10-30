# RealSense ROSbag to VRS Converter

**RealSense 型の ROSbag を、公式 VRS 実装を用いて RGB・深度・IMU・設定情報を含む VRS に変換します。**

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)

## 概要

書き込みには、PyPI パッケージ [`vrs`](https://pypi.org/project/vrs/) に含まれる公式 `vrsbindings.Writer` を使用します。自作 C++ ライターや VRS サブモジュールは不要です。PyVRS の公開名を書き換える補正処理も使用しません。

既定の保存形式バージョン 2 では、RGB・深度を本来の寸法と画素型の画像ブロック、IMU を数値メタデータとして記録します。論理ストリーム番号やセンサー設定は、このリポジトリの規約に従うタグに保持します。**VRS ファイルとして読めることと、Project Aria などの機器固有のデータ定義に適合することは別です。機器固有の互換性は保証していません。**

RGB と深度の画像コーデックは独立して選択できます。`raw`・PNG・JPEG と、深度専用方式を追加するための圧縮／復元インターフェースを提供します。圧縮画像は、現行の公式 Python API の制約に合わせ、保存形式バージョン 3 の明示的なメタデータ形式に格納します。標準の JPEG/PNG 画像ブロックではなく、外部ビューアーによる自動表示は保証しません。詳細は [RGB・深度の圧縮と復元](docs/IMAGE_CODECS.md) と [ADR-0001](docs/adr/0001-independent-image-codecs.md) を参照してください。

| 保存対象 | 論理ストリーム番号 | 内容 |
|---|---|---|
| Color | 1001 | 画像、寸法・画素形式、K・D・R・P、歪みモデル、frame_id、取得可能な StreamInfo |
| Depth | 1002 | 深度画像、カメラ情報、記録された Depth Units に基づく換算係数 |
| 加速度・角速度 | 1003・1004 | 各3成分、単位、frame_id、記録された取得頻度 |
| Transform | 1005・1006 | Depth・Color の並進とクォータニオン |
| Device Info | 2001 | デバイス名、製造番号、ファームウェア情報など |
| Sensor Info | 2002～2004 | センサー名、対応する論理ストリーム |
| Options | 2005 | センサー別の設定値と説明。設定のみで Data レコードは作成しません |

赤外線画像とフレームごとの追加メタデータは未対応です。ROSbag の全フィールドを保存する実装ではありません。入力は `rosbags.highlevel.AnyReader` を利用しますが、現在の本物のファイルを使う一連の回帰テストは **ROS1 の RealSense 型トピック**を対象としています。任意の ROS2 記録の互換性を保証するものではありません。

## 人工データによるクイックスタート

カメラや実収録データは必要ありません。人工 bag を一時ディレクトリに生成し、実際の VRS へ変換できます。

```bash
git clone https://github.com/yuki-inaho/realsense_rosbag_vrs_sandbox.git
cd realsense_rosbag_vrs_sandbox
uv sync --locked --group dev

VRS_DEMO_DIR=$(mktemp -d)
uv run python -m scripts.synthetic_rosbag "$VRS_DEMO_DIR/synthetic.bag"
uv run python convert_to_vrs.py "$VRS_DEMO_DIR/synthetic.bag" "$VRS_DEMO_DIR/synthetic.vrs" --imu --compression zstd
uv run python inspect_vrs.py "$VRS_DEMO_DIR/synthetic.vrs" --verbose
```

生成器の既定値は **640×480、RGB-D 各4フレーム、加速度・角速度各4件**です。校正、外部パラメータ、人工のデバイス情報・設定値も含みます。実収録ファイルを読み取ったり、ネットワークからデータを取得したりしません。生成器は既存ファイルへの上書きを拒否します。`*.bag` と `*.vrs` は Git の対象外です。

生成オプションとテストの合格条件は [人工 ROSbag と一連の変換テスト](docs/SYNTHETIC_E2E.md) に記載しています。

## 環境とバージョン

- Python の指定は `.python-version` の **3.10.6**、許容条件は **3.10.6 以上**です。
- `uv.lock` が固定する PyVRS は **1.2.2** です。2026年10月30日の確認時点で、[公式の最新公開版](https://github.com/facebookresearch/pyvrs/releases/tag/v1.2.2)と一致します。開発中の `main` の版番号とは区別しています。
- [PyVRS 1.2.2 のソース](https://github.com/facebookresearch/pyvrs/tree/v1.2.2/csrc)が参照する C++ VRS は、ソースの `version.txt` 上で **1.4.0** です。これはインストール済みバイナリの厳密なビルド元を同定する情報ではありません。
- Python 3.10 を継続できるよう、NumPy は `>=1.24.0,<2.3`、固定版は **2.2.6** です。
- 通常の開発・テストには Linux x86-64 を使用します。利用可能なバイナリ配布物は [PyPI](https://pypi.org/project/vrs/1.2.2/#files) で確認できます。

主要依存は [pyproject.toml](pyproject.toml)、固定された依存構成は [uv.lock](uv.lock) を参照してください。パッケージ自身の版は **0.1.0**、既定の RAW 保存は **版2**、圧縮画像ストリームは **版3** です。

## 変換と確認

`--imu` を指定すると、加速度・角速度と Device／Sensor／Options の保存も有効になります。通常の RGB-D 構成には Transform を含みます。

```bash
uv run python convert_to_vrs.py INPUT.bag OUTPUT.vrs --imu --compression lz4
uv run python inspect_vrs.py OUTPUT.vrs --stream 1001 --verbose
uv run python inspect_vrs.py OUTPUT.vrs --json
```

VRS レコードの圧縮は `none`・`lz4`・`zstd` に対応します。画像の行余白とバイト順は解釈してから保存し、解像度・画像形式・ペイロード長の不一致はエラーにします。

画像自体の圧縮は、RGB を `--color-codec raw|png|jpeg`、深度を `--depth-codec raw|png` で選択します。既定はいずれも `raw` です。JPEG の品質や PNG の圧縮レベルは、それぞれの `--color-codec-options`／`--depth-codec-options` に JSON で指定します。復元方式と設定はファイル内に保存されるため、読み出し時の再指定は不要です。深度は可逆方式のみとし、float32 を PNG 用に黙って整数化することはありません。

```bash
uv run python convert_to_vrs.py INPUT.bag OUTPUT.vrs --imu \
  --color-codec jpeg --color-codec-options '{"quality":90}' \
  --depth-codec png --depth-codec-options '{"compression_level":3}' \
  --compression zstd
```

深度の換算係数は、そのセンサーに記録された `Depth Units` から取得します。記録がない場合は `0.001` を使用し、設定の `depth_scale_source` に `default_millimeters` と明示します。IMU の取得頻度は StreamInfo がある場合に保存し、不明な場合の `sample_rate` は `null` です。

## テスト

```bash
# 実収録データが不要な全回帰。一連の変換テストも含みます。
uv run pytest -q -m "not integration"

# 人工 ROSbag → 変換 CLI → 公式 PyVRS リーダーの検証
uv run pytest -q -m e2e

# 利用者が手元で明示指定する実収録 bag の検証
REALSENSE_ROSBAG_PATH=/absolute/path/to/sample.bag uv run pytest -q -m integration
```

従来の一連の変換テストでは **640×480×12フレーム**を生成し、3種類のレコード圧縮で全画素・全 IMU 成分・時刻・校正・外部パラメータ・設定を比較します。12フレーム分は既定の 16 MiB 書き出し閾値を超えるため、途中の書き出し後にもレコードが欠落しないことを確認します。期待値は入力 bag から独立に読み出し、出力はリポジトリのリーダーを介さず公式 PyVRS で検査します。

画像コーデックの E2E は **640×480×3フレーム、RGB3方式×深度2方式×レコード圧縮3方式の18組合せ**を追加検証します。標準ライブラリによる独立した PNG/JPEG 復元と、プロジェクトの復元 API の両方を確認します。独自の深度方式についても、別実装の圧縮器・復元器を登録する契約テストがあります。詳細は [画像コーデックのテスト](docs/IMAGE_CODECS.md#テスト) を参照してください。

[GitHub Actions の設定](.github/workflows/tests.yml)は Python 3.10.6 と 3.12 で固定依存、静的検査、実収録不要のテストを実行します。個々の実行の合否は Actions の実行結果で確認してください。

## 実装の構成

| ファイル | 役割 |
|---|---|
| [scripts/synthetic_rosbag.py](scripts/synthetic_rosbag.py) | 人工 ROS1 bag の生成 |
| [scripts/rosbag_to_vrs_converter.py](scripts/rosbag_to_vrs_converter.py) | 設定取得、画像・IMU の変換、統計 |
| [scripts/image_payload.py](scripts/image_payload.py) | ROS 画像の寸法・行余白・バイト順の検証と正規化 |
| [scripts/image_codecs.py](scripts/image_codecs.py) | 圧縮／復元の契約、方式と設定、明示的な登録表 |
| [scripts/image_codec_builtin.py](scripts/image_codec_builtin.py) | RAW・PNG・JPEG の実装 |
| [scripts/image_codec_storage.py](scripts/image_codec_storage.py) | 圧縮画像と VRS 保存形式の接続 |
| [scripts/vrs_writer.py](scripts/vrs_writer.py) | 公式ライターを用いた画像・数値・バイト列の保存 |
| [scripts/vrs_schema.py](scripts/vrs_schema.py) | 保存形式バージョン2と共通タグの定義 |
| [scripts/vrs_reader.py](scripts/vrs_reader.py) | 現行形式と過去の形式の読み出し、画像の復元 |
| [tests/test_synthetic_e2e.py](tests/test_synthetic_e2e.py) | 従来の実 bag／VRS を使う独立検証 |
| [tests/test_image_codec_e2e.py](tests/test_image_codec_e2e.py) | コーデックの組合せと深度専用拡張の検証 |

過去の1行 GREY8 保存形式と CUSTOM ブロックを読む互換処理は残しています。旧 GREY8 形式はテスト時に再生成して検証します。過去のすべての収録ファイルの互換性を確認したわけではありません。

## ドキュメント

- [RGB・深度の圧縮と復元](docs/IMAGE_CODECS.md)
- [ADR-0001: 画像コーデックとVRS保存処理の分離](docs/adr/0001-independent-image-codecs.md)
- [人工 ROSbag と一連の変換テスト](docs/SYNTHETIC_E2E.md)
- [実装詳細](docs/IMPLEMENTATION.md)
- [VRS API チートシート](docs/VRS_API_CHEATSHEET.md)
- [2025年の作業記録](docs/work_plan_rosbag_to_vrs_nov19_2025.md)：過去の設計と経緯。現行仕様は上記文書を参照してください。

## ライセンスと参照先

従来のライセンス説明は Apache 2.0 です。依存ライブラリについては各公式リポジトリのライセンスを参照してください。

- [VRS](https://github.com/facebookresearch/vrs)
- [PyVRS](https://github.com/facebookresearch/pyvrs)
- [rosbags](https://gitlab.com/ternaris/rosbags)

**更新日:** 2026-10-30

**パッケージ版:** 0.1.0

**保存形式版:** 2（既定のRAW画像）／3（圧縮画像）
