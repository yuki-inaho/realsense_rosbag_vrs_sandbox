# RGB・深度の圧縮と復元

設計判断は [ADR-0001](adr/0001-independent-image-codecs.md) を参照してください。

## 方式を個別に指定する

画像圧縮とVRSレコード圧縮は独立した設定です。既定の画像方式は従来どおり `raw` です。

```bash
uv sync --locked --group dev
WORK_DIR=$(mktemp -d)
uv run python -m scripts.synthetic_rosbag "$WORK_DIR/input.bag" --frames 12
uv run python convert_to_vrs.py "$WORK_DIR/input.bag" "$WORK_DIR/output.vrs" \
  --imu --color-codec jpeg --color-codec-options '{"quality":90}' \
  --depth-codec png --depth-codec-options '{"compression_level":3}' \
  --compression zstd
uv run python inspect_vrs.py "$WORK_DIR/output.vrs" --verbose
```

実収録ファイルは使用しません。生成されたbag/VRSは一時ディレクトリ内に置き、コミットしません。

| 項目 | 値・意味 |
|---|---|
| `--color-codec` | `raw` / `png` / `jpeg`。既定はraw |
| `--depth-codec` | `raw` / `png`。既定はraw |
| `--color-codec-options` | RGB側のJSON設定 |
| `--depth-codec-options` | 深度側のJSON設定 |
| JPEGの `quality` | 整数1～100、既定95。非可逆です |
| PNGの `compression_level` | 整数0～9、既定3。画素値の精度は変わりません |
| `--compression` | VRSレコードの `none` / `lz4` / `zstd`。既定lz4 |

rawは設定値を受け付けません。方式に無関係な設定、未知の設定、不正な値は無視せずエラーにします。PNGは8bit/16bit整数、JPEGは8bitのRGB/BGR/単色に対応します。float32深度をPNGに渡して丸めることや、アルファをJPEGで黙って捨てることは行いません。

## Python API

`image_codecs` は論理ストリームIDをキーとする設定表です。省略した画像ストリームはrawのままです。

```python
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from scripts.image_codecs import CodecSpec
from scripts.vrs_reader import VRSReader
from scripts.vrs_writer import VRSWriter

with TemporaryDirectory() as directory:
    output = Path(directory) / "images.vrs"
    color = np.zeros((6, 8, 3), dtype=np.uint8)
    color[..., 0] = 200
    depth = np.arange(48, dtype="<u2").reshape(6, 8)
    depth[0, 0], depth[-1, -1] = 0, 65535
    with VRSWriter(
        output,
        compression="lz4",
        image_codecs={
            1001: CodecSpec("jpeg", options={"quality": 90}),
            1002: CodecSpec("png", options={"compression_level": 3}),
        },
    ) as writer:
        writer.add_stream(1001, "Color")
        writer.add_stream(1002, "Depth")
        writer.write_configuration(1001, {"width": 8, "height": 6, "encoding": "rgb8"})
        writer.write_configuration(
            1002, {"width": 8, "height": 6, "encoding": "16UC1", "depth_scale": 0.002}
        )
        writer.write_data(1001, 1.0, color.tobytes())
        writer.write_data(1002, 1.0, depth.tobytes())

    with VRSReader(output) as reader:
        # 復元方式・設定はファイルから取得され、再指定は不要です。
        restored = next(reader.read_data_records(1002))["data"]
        assert restored == depth.tobytes()
        # 圧縮データを取り出すAPIは、画素データのAPIと明確に分離します。
        encoded = next(reader.read_encoded_image_records(1001))
        assert encoded["descriptor"].codec.name == "jpeg"
        assert encoded["data"].startswith(b"\xff\xd8")
```

`read_data_records()` の画像データは復元後のバイト列です。JPEGでは元の画素と完全一致しません。`read_encoded_image_records()` は保存版3の圧縮画像専用で、未圧縮画像に対して呼ぶとエラーです。

## 深度専用方式を追加する

追加箇所は圧縮器、復元器、その登録、契約テストです。ライター・リーダー・ROSbag変換器の方式分岐を変更する必要はありません。

| インターフェース | 実装するメソッド |
|---|---|
| `ImageEncoder` | `validate(ImageSpec)`、`encode(pixels, ImageSpec) -> bytes` |
| `ImageDecoder` | `validate(ImageSpec)`、`decode(bytes, ImageSpec) -> ndarray` |

`CodecRegistry.register_encoder(name, version, factory, lossless=True)` と `register_decoder(name, version, factory)` に別々に登録し、`VRSWriter(..., codec_registry=registry)`／`VRSReader(..., codec_registry=registry)` へ渡します。登録の `factory` は `CodecSpec` を受け取り、対応する実装を返します。読み出し専用環境は復元器だけを登録できます。

実装例と動作確認は `tests/test_image_codec_e2e.py` の `_DepthEncoder`、`_IndependentDepthDecoder`、`test_injected_depth_encoder_and_separate_decoder_roundtrip` にあります。例はテスト専用の方式です。独立した圧縮／復元実装でuint16の0・65535、float32のNaN・Inf・符号付きゼロまで確認します。

独自実装では次を契約に含めてください。

- 安定した方式IDと版番号、対応する元の画素形式、設定値の検証。
- 深度の単位・無効値・NaN等の扱い。現在は可逆方式のみ受け付けます。
- 入力を変更しないこと、各フレームを単独で復元できること、割当量の上限を検査すること。

汎用の手動入力では、設定に `image_role="depth"` を指定できます。既存のRealSense変換器は `depth_scale` を持つ設定を生成するため、自動的に深度として扱います。

ROSbag変換APIでは既存の `writer_factory` に `functools.partial(VRSWriter, image_codecs=..., codec_registry=..., compression=...)` を渡します。CLIから任意のPythonモジュールを自動読込みする機構はありません。独自方式のCLI公開は、信頼できるアプリケーション側で登録した上で行います。

## 保存形式の留意点

現在の固定依存の公式Pythonライターは、RAW以外の画像ブロックを任意に作るAPIを公開していません。そのため圧縮画像は、公式メタデータレコードの文字列内へBase64として保存し、`image_codec_json` タグに復元条件を記録します。

これは**JPEG/PNGの標準VRS画像ブロックではありません**。外部ビューアーによる自動表示は保証しません。公式リーダーから取り出し、標準のJPEG/PNGライブラリで復元できることをE2Eで確認します。Base64によるサイズ増加・文字列化の費用もあります。

RAWのみの出力は保存版2を維持します。圧縮画像ストリームは保存版3であり、旧リーダーは対応しません。新しいリーダーは従来の保存版2とタグなしの旧形式も読みます。圧縮方式不明、未対応版、破損した設定・型・形状はエラーとし、RAWへの黙示的な切り替えはしません。

## テスト

```bash
# 圧縮方式の契約と、実bag/実VRSの入出力
uv run pytest -q tests/test_image_codecs.py tests/test_image_codec_e2e.py

# 旧形式・従来E2Eも含めた、実収録不要の全回帰
uv run pytest -q -m "not integration"
```

E2Eは640×480、各3フレームで、RGB3方式×深度2方式×VRSレコード圧縮3方式の18組合せを比較します。さらに行余白付き・ビッグエンディアン深度、設定エラー、復元器未導入、独自深度方式、書き出し境界と同時刻レコードを検査します。

本物のROSbagとVRSを使用しますが、データは人工生成します。特定の実機収録、任意のROS2トピック構成、全コーデック実装の性能や精度を保証するものではありません。
