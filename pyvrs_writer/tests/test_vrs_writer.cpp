// pyvrs_writer/tests/test_vrs_writer.cpp
#include <gtest/gtest.h>
#include "vrs_writer.h"
#include <filesystem>

namespace fs = std::filesystem;

class VRSWriterTest : public ::testing::Test {
protected:
  void SetUp() override {
    testFilePath_ = "/tmp/test_vrs_writer.vrs";
    // テストファイルが存在する場合は削除
    if (fs::exists(testFilePath_)) {
      fs::remove(testFilePath_);
    }
  }

  void TearDown() override {
    // テストファイルをクリーンアップ
    if (fs::exists(testFilePath_)) {
      fs::remove(testFilePath_);
    }
  }

  std::string testFilePath_;
};

TEST_F(VRSWriterTest, ConstructorCreatesFile) {
  pyvrs_writer::VRSWriter writer(testFilePath_);
  EXPECT_TRUE(writer.isOpen());
}

TEST_F(VRSWriterTest, AddStream) {
  pyvrs_writer::VRSWriter writer(testFilePath_);
  EXPECT_NO_THROW(writer.addStream(1001, "RGB Camera"));
}

TEST_F(VRSWriterTest, WriteConfiguration) {
  pyvrs_writer::VRSWriter writer(testFilePath_);
  writer.addStream(1001, "RGB Camera");
  std::string config = R"({"width": 640, "height": 480})";
  EXPECT_NO_THROW(writer.writeConfiguration(1001, config));
}

TEST_F(VRSWriterTest, WriteData) {
  pyvrs_writer::VRSWriter writer(testFilePath_);
  writer.addStream(1001, "RGB Camera");
  std::vector<uint8_t> data = {0x01, 0x02, 0x03};
  EXPECT_NO_THROW(writer.writeData(1001, 0.0, data));
}

TEST_F(VRSWriterTest, CloseFile) {
  pyvrs_writer::VRSWriter writer(testFilePath_);
  writer.close();
  EXPECT_FALSE(writer.isOpen());
}

TEST_F(VRSWriterTest, FileExistsAfterClose) {
  {
    pyvrs_writer::VRSWriter writer(testFilePath_);
    writer.addStream(1001, "Test");
    writer.close();
  }
  EXPECT_TRUE(fs::exists(testFilePath_));
}
