# pyvrs_writer/python_tests/test_pyvrs_writer.py
"""Tests for pyvrs_writer Python bindings."""

import pytest
from pathlib import Path
import tempfile
import os

try:
    from pyvrs_writer import VRSWriter
except ImportError:
    pytest.skip("pyvrs_writer not installed", allow_module_level=True)


@pytest.fixture
def temp_vrs_file():
    """Create a temporary VRS file path."""
    with tempfile.NamedTemporaryFile(suffix='.vrs', delete=False) as f:
      temp_path = f.name
    yield temp_path
    # Cleanup
    if os.path.exists(temp_path):
        os.remove(temp_path)


def test_vrs_writer_creation(temp_vrs_file):
    """Test VRSWriter can be created."""
    writer = VRSWriter(temp_vrs_file)
    assert writer.is_open()
    writer.close()


def test_vrs_writer_context_manager(temp_vrs_file):
    """Test VRSWriter works as context manager."""
    with VRSWriter(temp_vrs_file) as writer:
        assert writer.is_open()

    # After exiting context, file should be closed
    assert not writer.is_open()


def test_add_stream(temp_vrs_file):
    """Test adding a stream."""
    with VRSWriter(temp_vrs_file) as writer:
        writer.add_stream(1001, "RGB Camera")
        # No exception should be raised


def test_write_configuration(temp_vrs_file):
    """Test writing configuration."""
    with VRSWriter(temp_vrs_file) as writer:
        writer.add_stream(1001, "RGB Camera")
        config = '{"width": 640, "height": 480}'
        writer.write_configuration(1001, config)


def test_write_data(temp_vrs_file):
    """Test writing data."""
    with VRSWriter(temp_vrs_file) as writer:
        writer.add_stream(1001, "Test Stream")
        data = [0x01, 0x02, 0x03, 0x04]
        writer.write_data(1001, 0.0, data)


def test_file_exists_after_close(temp_vrs_file):
    """Test VRS file exists after closing."""
    with VRSWriter(temp_vrs_file) as writer:
        writer.add_stream(1001, "Test")

    assert os.path.exists(temp_vrs_file)
    assert os.path.getsize(temp_vrs_file) > 0
