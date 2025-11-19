// pyvrs_writer/include/vrs_writer.h
#pragma once

#include <string>
#include <memory>
#include <vector>
#include <cstdint>

namespace pyvrs_writer {

class VRSWriter {
public:
  VRSWriter(const std::string& filepath);
  ~VRSWriter();

  // ストリームの追加
  void addStream(uint32_t streamId, const std::string& streamName);

  // Configurationレコードの書き込み
  void writeConfiguration(uint32_t streamId, const std::string& jsonConfig);

  // Dataレコードの書き込み
  void writeData(uint32_t streamId, double timestamp, const std::vector<uint8_t>& data);

  // ファイルのクローズ
  void close();

  // ファイルが開いているか確認
  bool isOpen() const;

private:
  class Impl;
  std::unique_ptr<Impl> pImpl_;
};

}  // namespace pyvrs_writer
