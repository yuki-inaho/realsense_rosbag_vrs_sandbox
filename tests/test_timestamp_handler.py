"""Tests for timestamp handling functionality."""

from datetime import datetime, timezone

import pytest


class TestTimestampHandler:
    """Test cases for timestamp conversion and formatting."""

    def test_ros_timestamp_to_seconds(self) -> None:
        """Test converting ROS timestamp to seconds (float)."""
        from scripts.timestamp_handler import ros_timestamp_to_seconds

        # ROS timestamp: nanoseconds since epoch
        ros_timestamp_ns = 1000000000  # 1 second in nanoseconds
        result = ros_timestamp_to_seconds(ros_timestamp_ns)

        assert isinstance(result, float)
        assert result == pytest.approx(1.0, rel=1e-9)

    def test_ros_timestamp_to_datetime(self) -> None:
        """Test converting ROS timestamp to Python datetime object."""
        from scripts.timestamp_handler import ros_timestamp_to_datetime

        # Unix epoch + 1 second
        ros_timestamp_ns = 1000000000
        result = ros_timestamp_to_datetime(ros_timestamp_ns)

        assert isinstance(result, datetime)
        assert result.year == 1970
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 1
        assert result.tzinfo == timezone.utc

    def test_format_timestamp_iso(self) -> None:
        """Test formatting timestamp to ISO 8601 string."""
        from scripts.timestamp_handler import format_timestamp_iso

        # Create a known datetime
        dt = datetime(2023, 11, 19, 12, 30, 45, 123456, tzinfo=timezone.utc)
        result = format_timestamp_iso(dt)

        assert isinstance(result, str)
        assert "2023-11-19" in result
        assert "12:30:45" in result

    def test_timestamp_roundtrip(self) -> None:
        """Test that conversion is reversible."""
        from scripts.timestamp_handler import (
            ros_timestamp_to_datetime,
            ros_timestamp_to_seconds,
        )

        original_ns = 1700000000000000000  # A recent timestamp
        dt = ros_timestamp_to_datetime(original_ns)
        seconds = ros_timestamp_to_seconds(original_ns)

        # Verify the conversion preserves information
        assert dt.timestamp() == pytest.approx(seconds, rel=1e-6)

    def test_zero_timestamp(self) -> None:
        """Test handling of zero timestamp (edge case)."""
        from scripts.timestamp_handler import ros_timestamp_to_datetime

        result = ros_timestamp_to_datetime(0)

        assert isinstance(result, datetime)
        assert result.year == 1970
        assert result.month == 1
        assert result.day == 1

    def test_high_precision_preservation(self) -> None:
        """Test that nanosecond precision is preserved in conversion."""
        from scripts.timestamp_handler import ros_timestamp_to_seconds

        # Timestamp with nanosecond precision
        ros_timestamp_ns = 1234567890123456789
        result = ros_timestamp_to_seconds(ros_timestamp_ns)

        # Check that we maintain at least microsecond precision
        expected_seconds = 1234567890.123456789
        assert result == pytest.approx(expected_seconds, rel=1e-9)
