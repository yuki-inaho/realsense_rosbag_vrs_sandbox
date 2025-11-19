# pyvrs_writer/tests/CMakeLists.txt

add_executable(vrs_writer_test
  test_vrs_writer.cpp
)

target_link_libraries(vrs_writer_test
  vrs_writer_core
  GTest::gtest
  GTest::gtest_main
)

add_test(NAME VRSWriterTest COMMAND vrs_writer_test)
