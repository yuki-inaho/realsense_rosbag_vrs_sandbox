"""Tests for VRS Writer module.

This module contains unit tests for the VRS Writer wrapper class,
which provides a Pythonic interface to the pyvrs_writer C++ bindings.
"""

import pytest
from pathlib import Path


def test_vrs_writer_initialization(tmp_path: Path) -> None:
    """VRSWriterが正しく初期化されること."""
    from scripts.vrs_writer import VRSWriter

    vrs_file = tmp_path / "test.vrs"
    writer = VRSWriter(vrs_file)
    assert writer is not None
    writer.close()
    assert vrs_file.exists()


def test_vrs_writer_context_manager(tmp_path: Path) -> None:
    """コンテキストマネージャとして使用できること."""
    from scripts.vrs_writer import VRSWriter

    vrs_file = tmp_path / "test.vrs"
    with VRSWriter(vrs_file) as writer:
        assert writer is not None
    assert vrs_file.exists()


def test_add_stream(tmp_path: Path) -> None:
    """ストリームを追加できること."""
    from scripts.vrs_writer import VRSWriter

    vrs_file = tmp_path / "test.vrs"
    with VRSWriter(vrs_file) as writer:
        writer.add_stream(1001, "Test Stream")
        # ストリーム追加の検証: is_open()で確認
        assert writer.is_open()


def test_write_configuration(tmp_path: Path) -> None:
    """Configurationレコードを書き込めること."""
    from scripts.vrs_writer import VRSWriter

    vrs_file = tmp_path / "test.vrs"
    with VRSWriter(vrs_file) as writer:
        writer.add_stream(1001, "Test Stream")
        config = {"width": 640, "height": 480, "encoding": "rgb8"}
        writer.write_configuration(1001, config)


def test_write_data(tmp_path: Path) -> None:
    """Dataレコードを書き込めること."""
    from scripts.vrs_writer import VRSWriter

    vrs_file = tmp_path / "test.vrs"
    with VRSWriter(vrs_file) as writer:
        writer.add_stream(1001, "Test Stream")
        # pyvrs_writerはlist[int]を期待するため、bytesをlistに変換
        test_data = b"test data"
        writer.write_data(1001, 0.0, test_data)
        test_data2 = b"test data 2"
        writer.write_data(1001, 0.033, test_data2)


def test_multiple_streams(tmp_path: Path) -> None:
    """複数のストリームを扱えること."""
    from scripts.vrs_writer import VRSWriter

    vrs_file = tmp_path / "test.vrs"
    with VRSWriter(vrs_file) as writer:
        writer.add_stream(1001, "Stream 1")
        writer.add_stream(1002, "Stream 2")
        writer.write_data(1001, 0.0, b"data1")
        writer.write_data(1002, 0.0, b"data2")


def test_is_open(tmp_path: Path) -> None:
    """is_open()メソッドが正しく動作すること."""
    from scripts.vrs_writer import VRSWriter

    vrs_file = tmp_path / "test.vrs"
    writer = VRSWriter(vrs_file)
    assert writer.is_open()
    writer.close()
    assert not writer.is_open()


def test_invalid_stream_id(tmp_path: Path) -> None:
    """無効なストリームIDでエラーが発生すること."""
    from scripts.vrs_writer import VRSWriter

    vrs_file = tmp_path / "test.vrs"
    with VRSWriter(vrs_file) as writer:
        writer.add_stream(1001, "Test Stream")
        # 存在しないストリームへの書き込みでエラー
        with pytest.raises((ValueError, RuntimeError)):
            writer.write_configuration(9999, {"test": "config"})


def test_duplicate_stream_id(tmp_path: Path) -> None:
    """重複したストリームIDでエラーが発生すること."""
    from scripts.vrs_writer import VRSWriter

    vrs_file = tmp_path / "test.vrs"
    with VRSWriter(vrs_file) as writer:
        writer.add_stream(1001, "Stream 1")
        # 同じIDで再度追加しようとするとエラー
        with pytest.raises((ValueError, RuntimeError)):
            writer.add_stream(1001, "Stream 2")


def test_write_data_before_adding_stream(tmp_path: Path) -> None:
    """ストリーム追加前のデータ書き込みでエラーが発生すること."""
    from scripts.vrs_writer import VRSWriter

    vrs_file = tmp_path / "test.vrs"
    with VRSWriter(vrs_file) as writer:
        # ストリーム追加なしでデータ書き込み
        with pytest.raises((ValueError, RuntimeError)):
            writer.write_data(1001, 0.0, b"data")
