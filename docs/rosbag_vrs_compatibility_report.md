# ROSbag → VRS 互換性検証レポート

**プロジェクト**: RealSense ROSbag → VRS 変換システム
**作成日**: 2025-11-19
**検証フェーズ**: Phase 1-4 (VRS読み取り検証 + ROSbag構造分析 + マッピング設計)
**作成者**: Claude (Sonnet 4.5)

---

## エグゼクティブサマリー

本レポートは、RealSense D435i ROSbagデータをVRSフォーマットに変換するための互換性検証結果を報告します。Phase 1-4（VRS C++ API調査、C++ VRS読み取り検証、ROSbag構造分析、ROSbag→VRSマッピング設計）を完了し、以下の成果を達成しました：

### 主要成果

- ✅ **VRS RecordFormat/DataLayout読み取り検証完了**: C++ VRSReaderでPhase 3実装版が正常に読み取れることを確認
- ✅ **ROSbag構造分析完了**: RealSense D435i標準トピック構造（6トピック）を文書化
- ✅ **ROSbag→VRSマッピング設計完了**: 4ストリーム定義、6 DataLayoutクラス設計、実装優先順位付け完了
- ✅ **Phase 4実装準備完了**: 次フェーズに必要な全技術情報を文書化

### リスクと制約

- ⚠️ **PyVRS pytest環境クラッシュ**: PyVRSはpytest環境で`currentLayout_ != nullptr` failedエラーが発生。C++ VRSReaderで回避可能。
- ⚠️ **実ROSbagファイル不在**: Git LFS削除により実ファイルでのテストは未実施。Phase 4実装時に実データでの検証が必要。

---

## 1. 検証目的と範囲

### 1.1 検証目的

1. **Phase 3実装版VRSファイルの読み取り検証**: RecordFormat/DataLayout実装が正しく読み取れるか確認
2. **ROSbag構造の詳細分析**: RealSense D435i ROSbagのトピック構造、メッセージ型、フィールドを分析
3. **ROSbag→VRSマッピング設計**: ROSbagデータをVRSフォーマットに変換するための完全な設計仕様作成

### 1.2 検証範囲

- **対象センサー**: RealSense D435i (RGB Camera, Depth Camera, IMU Accel, IMU Gyro)
- **対象ROSbagトピック**: 6トピック (Color/Depth画像、CameraInfo×2、IMU Accel/Gyro)
- **対象VRSストリーム**: 4ストリーム (Color 1001, Depth 1002, IMU Accel 2001, IMU Gyro 2002)
- **実装手法**: C++ VRS API + pybind11 Python bindings

### 1.3 検証期間

- **開始**: 2025-11-19 09:21:15 UTC
- **完了**: 2025-11-19 09:32:40 UTC
- **総作業時間**: 約11分25秒（Phase 1-4完了）

---

## 2. 検証結果

### 2.1 Phase 1: VRS C++ API調査

#### 実施内容

- VRS公式サンプルコード読み込み（`SampleRecordFormatDataLayout.cpp`）
- `RecordFormatStreamPlayer` API仕様確認
- `RecordFileReader` 基本的な使用方法確認

#### 結果

✅ **成功**: `RecordFormatStreamPlayer`継承パターン、`onDataLayoutRead()`/`onCustomBlockRead()`実装パターンを確認。VRS C++ APIの基本的な使用方法を理解。

### 2.2 Phase 2: C++ VRS読み取りテストプログラム作成・実行

#### 実施内容

1. テストVRSファイル作成（`test_recordformat.py`、757 bytes）
2. C++ VRS読み取りプログラム作成（`test_vrs_cpp_reader.cpp`、115行）
3. コンパイル（g++、最終サイズ3.4MB）
4. 実行・動作検証

#### 結果

✅ **成功**: C++ VRSReaderでRecordFormat/DataLayout読み取りが完全動作確認。

**実行出力例**:
```
VRS file opened: /tmp/tmpxq8ihupk/test_recordformat.vrs
Number of streams: 1
  Stream ID: 1001-1

Reading all records...
  [DataLayout] stream=1001-1, type=CONFIGURATION, timestamp=0, blockIndex=0
    config_json: {"version": 1}
  [DataLayout] stream=1001-1, type=DATA, timestamp=1.23, blockIndex=0
    timestamp: 1.23
  [CustomBlock] stream=1001-1, type=DATA, timestamp=1.23, blockIndex=1, size=13 bytes
    data (first 20 bytes): 48 65 6c 6c 6f 2c 20 57 6f 72 6c 64 21
Done.
```

**期待出力との一致**: ✅ 完全一致
- Configuration RecordのDataLayout読み取り成功
- Data RecordのDataLayout読み取り成功
- CustomBlock読み取り成功（"Hello, World!"のバイナリ表示）

#### 技術的課題と解決策

**課題1: コンパイルエラー（`streams[0]`）**
- **エラー**: `no match for 'operator[]' (operand types are 'const std::set<vrs::StreamId>' and 'int')`
- **原因**: `std::set`は`[]`演算子をサポートしない
- **解決策**: `streams[0]` → `*streams.begin()` に変更

**課題2: リンクエラー（VRSライブラリ不足）**
- **エラー**: 多数のVRS関数が未定義参照エラー
- **解決策**: 以下のライブラリを全て明示的にリンク:
  ```bash
  -lvrslib -lvrs_utils -lvrs_utils_xxhash -lvrs_helpers -lvrs_logging -lvrs_os \
  -lboost_filesystem -lboost_system -lfmt -llz4 -lzstd -lxxhash -lpthread
  ```

### 2.3 Phase 3: ROSbag構造分析

#### 実施内容

- RealSense D435i標準トピック構造の文書化（実ファイル不在のため標準仕様に基づく）
- 6トピックの詳細分析（Color/Depth画像、CameraInfo×2、IMU Accel/Gyro）
- データ特性・座標系の文書化

#### 結果

✅ **成功**: `docs/rosbag_20251119_112125_structure.md` (133行、4.9KB) 作成完了。

**分析したトピック**:

| トピック名 | メッセージ型 | 周波数 | 解像度/特性 |
|-----------|------------|--------|-------------|
| `/device_0/sensor_1/Color_0/image/data` | `sensor_msgs/msg/Image` | ~30 Hz | 1920×1080, rgb8/bgr8 |
| `/device_0/sensor_0/Depth_0/image/data` | `sensor_msgs/msg/Image` | ~30 Hz | 1280×720, 16UC1 (mm) |
| `/device_0/sensor_1/Color_0/camera_info` | `sensor_msgs/msg/CameraInfo` | ~30 Hz | K行列、歪み係数D (5要素) |
| `/device_0/sensor_0/Depth_0/camera_info` | `sensor_msgs/msg/CameraInfo` | ~30 Hz | K行列、歪み係数D (5要素) |
| `/device_0/sensor_2/Accel_0/imu/data` | `sensor_msgs/msg/Imu` | ~63-250 Hz | linear_acceleration [m/s²] |
| `/device_0/sensor_2/Gyro_0/imu/data` | `sensor_msgs/msg/Imu` | ~200-400 Hz | angular_velocity [rad/s] |

**データ特性**:
- Color/Depth画像は時刻同期
- IMU Accel/Gyroは異なるサンプリングレート
- 各センサーは異なる座標系（frame_id）を持つ

#### 制約事項

⚠️ **実ROSbagファイル不在**: Git LFS削除により実ファイルでの詳細検証は未実施。Phase 4実装時に実データでの検証が必要。

### 2.4 Phase 4: ROSbag→VRSマッピング設計

#### 実施内容

1. RealSense D435i固有情報のマッピング定義
2. VRS ImageFormat/PixelFormat選択
3. VRS RecordableTypeId選定
4. DataLayout C++実装例作成
5. 実装優先順位付け

#### 結果

✅ **成功**: `docs/rosbag_vrs_mapping_design.md` (351行、12KB) 作成完了。

**定義した4ストリーム**:

| Stream ID | 名前 | RecordableTypeId | Stream Flavor | ROSbagソース |
|-----------|------|------------------|---------------|-------------|
| 1001 | Color Image | `ForwardCamera` | `RealSense_D435i_Color` | `/device_0/sensor_1/Color_0/image/data` |
| 1002 | Depth Image | `ForwardCamera` | `RealSense_D435i_Depth` | `/device_0/sensor_0/Depth_0/image/data` |
| 2001 | IMU Accelerometer | `MotionSensor` | `RealSense_D435i_IMU_Accel` | `/device_0/sensor_2/Accel_0/imu/data` |
| 2002 | IMU Gyroscope | `MotionSensor` | `RealSense_D435i_IMU_Gyro` | `/device_0/sensor_2/Gyro_0/imu/data` |

**DataLayout設計（6クラス）**:

1. **ColorImageConfigLayout**: width, height, encoding, camera_k, camera_d, distortion_model
2. **ColorImageDataLayout**: timestamp, frame_id
3. **DepthImageConfigLayout**: ColorImageConfigLayout + depth_scale
4. **DepthImageDataLayout**: timestamp, frame_id
5. **IMUConfigLayout**: sensor_type, sampling_rate, range, resolution
6. **IMU_AccelDataLayout**: timestamp, linear_acceleration (Point3Dd), frame_id
7. **IMU_GyroDataLayout**: timestamp, angular_velocity (Point3Dd), frame_id

**画像フォーマットマッピング**:

| ROSbag encoding | VRS ImageFormat | VRS PixelFormat | Bytes/Pixel |
|-----------------|-----------------|-----------------|-------------|
| `rgb8` | `RAW` | `RGB8` | 3 |
| `bgr8` | `RAW` | `BGR8` | 3 |
| `16UC1` | `RAW` | `GREY16` | 2 |

**実装優先順位**:

- **Phase 4A (必須)**: Stream 1001 (Color) + Stream 1002 (Depth)
- **Phase 4B (推奨)**: Stream 2001 (IMU Accel) + Stream 2002 (IMU Gyro)
- **Phase 4C (オプション)**: TF情報、メタデータ、診断情報

---

## 3. 既知の問題と制約

### 3.1 PyVRS pytest環境クラッシュ

**問題**: pytest実行時にPyVRSがクラッシュ（`currentLayout_ != nullptr` failed）

**詳細**:
```
Fatal Python error: Aborted
vrs/RecordFormat.cpp:117: void vrs::RecordFormat::setLayout(vrs::DataLayout*):
Assertion `currentLayout_ != nullptr' failed.
```

**影響**: Pythonでのテストコード（pytest環境）ではVRS読み取りができない

**回避策**:
- ✅ C++ VRSReaderを使用（`test_vrs_cpp_reader.cpp`で検証済み）
- ✅ Pythonスクリプト（非pytest環境）での手動実行は問題なし

**今後の対応**:
- Phase 4実装時はC++ VRSReaderで読み取り検証を行う
- PyVRSの問題はVRS公式リポジトリへの報告を検討

### 3.2 実ROSbagファイル不在

**問題**: `data/rosbag/20251119_112125.bag` が存在しない（Git LFS削除済み）

**影響**: 実データでのROSbag読み取り・変換テストが未実施

**回避策**: RealSense D435i標準トピック構造に基づいて設計を完了

**今後の対応**:
- Phase 4実装時に以下のいずれかの方法で実データを用意:
  1. Intel公式サンプルデータ（d435i_walk_around.bag, 803MB）をダウンロード
  2. 新たにRealSense D435iでROSbag記録
- 実データでの変換テスト・検証を実施

### 3.3 ImageブロックとDataLayoutの統合

**検討事項**: ImageブロックとDataLayoutを組み合わせる方法

**推奨方式**: DataLayout (metadata) + ImageBlock (pixel data)

**実装パターン**:
```cpp
// Record Format登録時
addRecordFormat(
    Record::Type::DATA,
    kDataVersion,
    dataLayout_.getContentBlock() + ContentBlock(ImageFormat::RAW),
    {&dataLayout_});

// レコード作成時
createRecord(
    timestamp,
    Record::Type::DATA,
    kDataVersion,
    DataSource(dataLayout_, {pixels.data(), pixels.size()}));
```

**参考**: `third/vrs/sample_code/SampleRecordFormatDataLayout.cpp`

---

## 4. 成果物一覧

| ファイル名 | 種別 | サイズ | 説明 |
|-----------|------|--------|------|
| `docs/rosbag_vrs_verification_plan_nov19.md` | ドキュメント | 818行 | 5フェーズ28ステップの詳細作業計画書（作業記録含む） |
| `docs/rosbag_20251119_112125_structure.md` | ドキュメント | 133行 | RealSense D435i ROSbagトピック構造分析書 |
| `docs/rosbag_vrs_mapping_design.md` | ドキュメント | 351行 | ROSbag→VRSマッピング設計仕様書 |
| `test_vrs_cpp_reader.cpp` | C++コード | 115行 | VRS RecordFormat読み取り検証プログラム |
| `test_vrs_cpp_reader` | 実行ファイル | 3.4MB | コンパイル済みC++ VRSリーダー |

---

## 5. 次フェーズへの推奨事項

### 5.1 Phase 4A: RGB-D変換実装（必須）

**優先度**: 最高
**実装対象**: Stream 1001 (Color) + Stream 1002 (Depth)

**実装ステップ**:
1. C++実装: `pyvrs_writer/src/vrs_writer.cpp` に以下を追加
   - `ColorImageConfigLayout` / `ColorImageDataLayout`
   - `DepthImageConfigLayout` / `DepthImageDataLayout`
   - `ColorCameraRecordable` / `DepthCameraRecordable` クラス

2. Python Binding: pybind11でPython側から使用可能にする
   ```cpp
   py::class_<ColorCameraRecordable>(m, "ColorCameraRecordable")
       .def(py::init<>())
       .def("add_configuration_record", ...)
       .def("add_data_record", ...);
   ```

3. ROSbag変換スクリプト: `scripts/convert_rosbag_to_vrs.py` 作成
   - `rosbags-py`でROSbagを読み取り
   - sensor_msgs/Imageメッセージをパース
   - VRSにConfiguration Record（1回）+ Data Records（各フレーム）を書き込み

4. テスト: 変換したVRSファイルをC++ VRS Readerで読み取り、データ完全性を検証

**期待成果**:
- RealSense D435i ROSbag → VRS変換が可能になる（RGB-Dデータのみ）
- VRSファイルサイズ：元ROSbagの50-70%程度を想定

### 5.2 Phase 4B: IMU変換実装（推奨）

**優先度**: 高
**実装対象**: Stream 2001 (IMU Accel) + Stream 2002 (IMU Gyro)

**実装ステップ**:
1. C++実装: IMUConfigLayout, IMU_AccelDataLayout, IMU_GyroDataLayout追加
2. Python Binding: IMU Recordableクラスをバインド
3. ROSbag変換スクリプト拡張: sensor_msgs/Imuメッセージをパース
4. テスト: IMUデータの完全性検証（サンプリングレート、値の範囲）

**期待成果**:
- 6DOF tracking、SLAM等のアプリケーションで使用可能なVRSファイル生成

### 5.3 Phase 4C: 追加情報実装（オプション）

**優先度**: 中
**実装対象**: TF情報、メタデータ、診断情報

**実装案**:
- TF情報: Configuration Recordに外部パラメータ（Extrinsics行列）を保存
- メタデータ: VRS Tags機能を使用してROSbag header情報を保存
- 診断情報: 別ストリームとしてROS diagnosticsトピックを保存

### 5.4 テスト戦略

**単体テスト** (pytest + gtest):
- VRSWriter各メソッドの入力検証
- DataLayout値の設定・取得
- 異常入力時のエラーハンドリング

**統合テスト** (C++ VRS Reader):
- 変換したVRSファイルを読み取り
- 元ROSbagデータと比較（画像ピクセル値、IMU値、タイムスタンプ）
- データ完全性検証

**性能テスト**:
- 変換速度測定（秒/フレーム）
- ファイルサイズ比較（VRS vs ROSbag）
- メモリ使用量プロファイリング

---

## 6. 結論

Phase 1-4（VRS読み取り検証、ROSbag構造分析、マッピング設計）を成功裏に完了しました。以下の成果により、Phase 4実装（ROSbag→VRS変換実装）に進む準備が整いました：

✅ **VRS RecordFormat/DataLayout読み取り動作確認完了**
✅ **ROSbag構造分析完了**（RealSense D435i標準6トピック）
✅ **ROSbag→VRSマッピング設計完了**（4ストリーム、6 DataLayout）
✅ **Phase 4実装計画明確化**（Phase 4A/4B/4Cの優先順位付け）

**推奨される次のアクション**:
1. 実ROSbagファイルを入手（Intel公式サンプルまたは新規記録）
2. Phase 4A（RGB-D変換）の実装を開始
3. C++ VRS Readerでの検証を継続実施

---

**作成者**: Claude (Sonnet 4.5)
**作成日時**: 2025-11-19 09:40 UTC
**バージョン**: 1.0
**関連ドキュメント**:
- `docs/rosbag_vrs_verification_plan_nov19.md` - 詳細作業計画書
- `docs/rosbag_20251119_112125_structure.md` - ROSbag構造分析書
- `docs/rosbag_vrs_mapping_design.md` - マッピング設計仕様書
- `docs/work_plan_rosbag_to_vrs_nov19_2025.md` - 全体プロジェクト計画書
