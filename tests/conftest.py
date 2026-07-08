"""Pytest configuration and shared fixtures."""

import os
from pathlib import Path

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark tests that consume real ROSbag fixtures as integration tests."""
    for item in items:
        fixture_names = getattr(item, "fixturenames", ())
        if "rosbag_path" in fixture_names or "sample_rosbag_path" in fixture_names:
            item.add_marker(pytest.mark.integration)


@pytest.fixture
def data_dir() -> Path:
    """Return the path to the test data directory."""
    return Path(__file__).parent.parent / "data"


@pytest.fixture
def rosbag_path(data_dir: Path) -> Path:
    """Return the path to the primary test ROSbag file (outdoor scene with IMU)."""
    path = Path(
        os.environ.get(
            "REALSENSE_ROSBAG_PATH",
            data_dir / "rosbag" / "d435i_walk_around.bag",
        )
    )
    if not path.exists():
        pytest.skip("real ROSbag not available; set REALSENSE_ROSBAG_PATH to run integration tests")
    return path


@pytest.fixture
def sample_rosbag_paths(data_dir: Path) -> dict[str, Path]:
    """Return paths to all available sample ROSbag files."""
    rosbag_dir = data_dir / "rosbag"
    return {
        "outdoor": rosbag_dir / "d435i_walk_around.bag",
        "walking": rosbag_dir / "sample_d435i.bag",
        "user_data": rosbag_dir / "20251119_112125.bag",
    }
