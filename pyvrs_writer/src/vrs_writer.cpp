// pyvrs_writer/src/vrs_writer.cpp
#include "vrs_writer.h"
#include <vrs/RecordFileWriter.h>
#include <vrs/Recordable.h>
#include <vrs/StreamId.h>
#include <vrs/DataLayout.h>
#include <vrs/DataPieces.h>
#include <vrs/RecordFormat.h>
#include <stdexcept>
#include <map>
#include <memory>

namespace pyvrs_writer {

// Configuration用DataLayout
class ConfigDataLayout : public vrs::AutoDataLayout {
public:
  vrs::DataPieceString configJson{"config_json"};
  vrs::AutoDataLayoutEnd endLayout;
};

// Data用DataLayout（メタデータ用、実データはCUSTOMブロック）
class DataRecordDataLayout : public vrs::AutoDataLayout {
public:
  vrs::DataPieceValue<double> timestamp{"timestamp"};
  vrs::AutoDataLayoutEnd endLayout;
};

// 簡易的なRecordableラッパークラス
class SimpleRecordable : public vrs::Recordable {
  static const uint32_t kConfigurationRecordFormatVersion = 1;
  static const uint32_t kDataRecordFormatVersion = 1;

public:
  SimpleRecordable(uint32_t streamId, const std::string& streamName)
    : vrs::Recordable(vrs::RecordableTypeId::UnitTest1, streamName),
      streamId_(streamId),
      configTimestamp_(0.0) {
    setRecordableIsActive(true);

    // RecordFormatを登録
    addRecordFormat(
        vrs::Record::Type::CONFIGURATION,
        kConfigurationRecordFormatVersion,
        configDataLayout_.getContentBlock(),
        {&configDataLayout_});
    addRecordFormat(
        vrs::Record::Type::DATA,
        kDataRecordFormatVersion,
        dataRecordDataLayout_.getContentBlock() + vrs::ContentBlock(vrs::ContentType::CUSTOM),
        {&dataRecordDataLayout_});
  }

  // Configuration JSONを設定
  void setConfigurationJson(const std::string& jsonConfig, double timestamp) {
    configJson_ = jsonConfig;
    configTimestamp_ = timestamp;
  }

  // データレコードを作成
  void addDataRecord(double timestamp, const std::vector<uint8_t>& data) {
    // DataLayoutにtimestampを設定
    dataRecordDataLayout_.timestamp.set(timestamp);

    // DataSource: DataLayout + CUSTOM data block
    vrs::DataSource dataSource(
        dataRecordDataLayout_,
        {data.data(), data.size()});
    createRecord(timestamp, vrs::Record::Type::DATA, kDataRecordFormatVersion, dataSource);
  }

  // Configuration recordを作成
  const vrs::Record* createConfigurationRecord() override {
    if (!configJson_.empty()) {
      // DataLayoutにJSON文字列を設定
      configDataLayout_.configJson.stage(configJson_);

      // DataSourceでDataLayoutを使用
      return createRecord(
          configTimestamp_,
          vrs::Record::Type::CONFIGURATION,
          kConfigurationRecordFormatVersion,
          vrs::DataSource(configDataLayout_));
    }
    // 空のConfiguration recordを返す
    return createRecord(0.0, vrs::Record::Type::CONFIGURATION, kConfigurationRecordFormatVersion);
  }

  // State recordを作成（最小限の実装）
  const vrs::Record* createStateRecord() override {
    // 空のState recordを返す（状態管理が不要な場合）
    return createRecord(0.0, vrs::Record::Type::STATE, 1);
  }

private:
  uint32_t streamId_;
  std::string configJson_;
  double configTimestamp_;
  ConfigDataLayout configDataLayout_;
  DataRecordDataLayout dataRecordDataLayout_;
};

class VRSWriter::Impl {
public:
  std::unique_ptr<vrs::RecordFileWriter> writer;
  std::map<uint32_t, std::unique_ptr<SimpleRecordable>> recordables;
  std::string filepath;
  bool isOpen = false;
};

VRSWriter::VRSWriter(const std::string& filepath)
  : pImpl_(std::make_unique<Impl>()) {
  pImpl_->writer = std::make_unique<vrs::RecordFileWriter>();
  pImpl_->filepath = filepath;
  pImpl_->isOpen = true;
}

VRSWriter::~VRSWriter() {
  if (pImpl_ && pImpl_->isOpen) {
    close();
  }
}

void VRSWriter::addStream(uint32_t streamId, const std::string& streamName) {
  if (!pImpl_->isOpen) {
    throw std::runtime_error("VRS file is not open");
  }

  auto recordable = std::make_unique<SimpleRecordable>(streamId, streamName);
  pImpl_->writer->addRecordable(recordable.get());
  pImpl_->recordables[streamId] = std::move(recordable);
}

void VRSWriter::writeConfiguration(uint32_t streamId, const std::string& jsonConfig) {
  if (!pImpl_->isOpen) {
    throw std::runtime_error("VRS file is not open");
  }

  // 対応するRecordableを検索
  auto it = pImpl_->recordables.find(streamId);
  if (it == pImpl_->recordables.end()) {
    throw std::runtime_error("Stream ID not found");
  }

  // Configuration JSONを設定し、Recordを作成
  // 注意: 同期書き込みモードでは明示的にcreateConfigurationRecord()を呼ぶ必要がある
  it->second->setConfigurationJson(jsonConfig, 0.0);
  it->second->createConfigurationRecord();
}

void VRSWriter::writeData(uint32_t streamId, double timestamp,
                          const std::vector<uint8_t>& data) {
  if (!pImpl_->isOpen) {
    throw std::runtime_error("VRS file is not open");
  }

  // 対応するRecordableを検索
  auto it = pImpl_->recordables.find(streamId);
  if (it == pImpl_->recordables.end()) {
    throw std::runtime_error("Stream ID not found");
  }

  // データレコードを作成（即座にRecordManagerに追加される）
  it->second->addDataRecord(timestamp, data);
}

void VRSWriter::close() {
  if (pImpl_->isOpen) {
    // writeToFileを使って同期的にファイルに書き込む
    int result = pImpl_->writer->writeToFile(pImpl_->filepath);
    if (result != 0) {
      throw std::runtime_error("Failed to write VRS file");
    }
    pImpl_->isOpen = false;
  }
}

bool VRSWriter::isOpen() const {
  return pImpl_->isOpen;
}

}  // namespace pyvrs_writer
