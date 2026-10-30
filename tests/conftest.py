"""Pytest configuration and shared fixtures."""

import os
from pathlib import Path

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark tests that consume real ROSbag fixtures as integration tests."""
    for item in items:
        fixture_names = getattr(item, "fixturenames", ())
        if "rosbag_path" in fixture_names:
            item.add_marker(pytest.mark.integration)


@pytest.fixture
def data_dir() -> Path:
    """Return the path to the test data directory."""
    return Path(__file__).parent.parent / "data"


@pytest.fixture
def rosbag_path() -> Path:
    """Use a user's recording only when they explicitly select it."""
    selected_path = os.environ.get("REALSENSE_ROSBAG_PATH")
    if not selected_path:
        pytest.skip("set REALSENSE_ROSBAG_PATH to run tests against a user recording")
    path = Path(selected_path)
    if not path.is_file():
        raise FileNotFoundError(f"REALSENSE_ROSBAG_PATH is not a file: {path}")
    return path
