"""Tests for VRS Reader module.

This module contains unit tests for the VRS Reader wrapper class,
which provides a Pythonic interface to the PyVRS library.
"""

import pytest
from pathlib import Path


@pytest.fixture
def sample_vrs_file(tmp_path: Path) -> Path:
    """テスト用のサンプルVRSファイルを作成."""
    from scripts.vrs_writer import VRSWriter

    vrs_file = tmp_path / "sample.vrs"
    with VRSWriter(vrs_file) as writer:
        writer.add_stream(1001, "Test Stream")
        writer.write_configuration(1001, {"key": "value", "width": 640})
        writer.write_data(1001, 0.0, b"data1")
        writer.write_data(1001, 0.033, b"data2")
        writer.write_data(1001, 0.066, b"data3")
    return vrs_file


def test_vrs_reader_initialization(sample_vrs_file: Path) -> None:
    """VRSReaderが正しく初期化されること."""
    from scripts.vrs_reader import VRSReader

    reader = VRSReader(sample_vrs_file)
    assert reader is not None
    reader.close()


def test_vrs_reader_context_manager(sample_vrs_file: Path) -> None:
    """コンテキストマネージャとして使用できること."""
    from scripts.vrs_reader import VRSReader

    with VRSReader(sample_vrs_file) as reader:
        assert reader is not None


def test_get_stream_ids(sample_vrs_file: Path) -> None:
    """ストリームID一覧を取得できること."""
    from scripts.vrs_reader import VRSReader

    with VRSReader(sample_vrs_file) as reader:
        stream_ids = reader.get_stream_ids()
        assert 1001 in stream_ids
        assert len(stream_ids) >= 1


def test_read_configuration(sample_vrs_file: Path) -> None:
    """Configurationレコードを読み込めること."""
    from scripts.vrs_reader import VRSReader

    with VRSReader(sample_vrs_file) as reader:
        config = reader.read_configuration(1001)
        assert config is not None
        assert "key" in config
        assert config["key"] == "value"


def test_read_data_records(sample_vrs_file: Path) -> None:
    """Dataレコードを読み込めること."""
    from scripts.vrs_reader import VRSReader

    with VRSReader(sample_vrs_file) as reader:
        records = list(reader.read_data_records(1001))
        assert len(records) == 3
        assert records[0]["timestamp"] == pytest.approx(0.0, abs=0.001)
        assert records[0]["data"] == b"data1"
        assert records[1]["timestamp"] == pytest.approx(0.033, abs=0.001)
        assert records[1]["data"] == b"data2"
        assert records[2]["timestamp"] == pytest.approx(0.066, abs=0.001)
        assert records[2]["data"] == b"data3"


def test_get_record_count(sample_vrs_file: Path) -> None:
    """レコード数を取得できること."""
    from scripts.vrs_reader import VRSReader

    with VRSReader(sample_vrs_file) as reader:
        count = reader.get_record_count(1001)
        assert count == 3


def test_invalid_stream_id(sample_vrs_file: Path) -> None:
    """存在しないストリームIDでエラーが発生すること."""
    from scripts.vrs_reader import VRSReader

    with VRSReader(sample_vrs_file) as reader:
        with pytest.raises((ValueError, RuntimeError, KeyError)):
            reader.read_configuration(9999)


def test_file_not_found() -> None:
    """存在しないファイルでエラーが発生すること."""
    from scripts.vrs_reader import VRSReader

    with pytest.raises((FileNotFoundError, ValueError, RuntimeError)):
        VRSReader("/nonexistent/path/to/file.vrs")
