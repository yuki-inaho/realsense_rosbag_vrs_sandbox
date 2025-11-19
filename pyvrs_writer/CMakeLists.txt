# pyvrs_writer/CMakeLists.txt
cmake_minimum_required(VERSION 3.10)
project(pyvrs_writer VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Threads検索
find_package(Threads REQUIRED)

# Boost Filesystemの検索
find_package(Boost REQUIRED COMPONENTS filesystem system)

# fmtライブラリの検索
find_package(fmt REQUIRED)

# 圧縮ライブラリ
find_library(LZ4_LIBRARY NAMES lz4 REQUIRED)
find_library(ZSTD_LIBRARY NAMES zstd REQUIRED)
find_library(XXHASH_LIBRARY NAMES xxhash REQUIRED)

# VRSライブラリのパスを設定
set(VRS_INSTALL_DIR "${CMAKE_SOURCE_DIR}/../third/vrs_install")
set(VRS_INCLUDE_DIR "${VRS_INSTALL_DIR}/include")
set(VRS_LIB_DIR "${VRS_INSTALL_DIR}/lib")

# pybind11の追加
find_package(pybind11 CONFIG)
if(NOT pybind11_FOUND)
  # fallback: pip install pybind11でインストールされたpybind11を使用
  execute_process(
    COMMAND python3 -m pybind11 --cmakedir
    OUTPUT_VARIABLE pybind11_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
  )
  find_package(pybind11 CONFIG REQUIRED)
endif()

# インクルードディレクトリ
include_directories(
  ${CMAKE_SOURCE_DIR}/include
  ${VRS_INCLUDE_DIR}
)

# VRSWriterラッパーライブラリ
add_library(vrs_writer_core STATIC
  src/vrs_writer.cpp
)

# pybind11用に-fPICフラグを追加
set_target_properties(vrs_writer_core PROPERTIES POSITION_INDEPENDENT_CODE ON)

target_link_libraries(vrs_writer_core
  -Wl,--start-group
  ${VRS_LIB_DIR}/libvrslib.a
  ${VRS_LIB_DIR}/libvrs_utils.a
  ${VRS_LIB_DIR}/libvrs_utils_xxhash.a
  ${VRS_LIB_DIR}/libvrs_os.a
  ${VRS_LIB_DIR}/libvrs_helpers.a
  ${VRS_LIB_DIR}/libvrs_logging.a
  ${VRS_LIB_DIR}/libocean_cv.a
  ${VRS_LIB_DIR}/libocean_math.a
  ${VRS_LIB_DIR}/libocean_base.a
  -Wl,--end-group
  Boost::filesystem
  Boost::system
  fmt::fmt
  ${LZ4_LIBRARY}
  ${ZSTD_LIBRARY}
  ${XXHASH_LIBRARY}
  Threads::Threads
)

# pybind11バインディング
pybind11_add_module(_pyvrs_writer
  src/bindings.cpp
)

target_link_libraries(_pyvrs_writer PRIVATE
  vrs_writer_core
)

# gtestの追加（オプション）
option(BUILD_TESTS "Build tests" ON)
if(BUILD_TESTS)
  enable_testing()
  find_package(GTest)
  if(GTest_FOUND)
    add_subdirectory(tests)
  endif()
endif()
