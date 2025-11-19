#!/usr/bin/env python3
"""Stream RealSense RGB-D-IR and IMU data from ROS bag files with time synchronization.

This script reads ROS bag files containing RealSense camera data and streams
sensor data in chronological order with optional timestamp filtering.

Usage:
    # Stream all data
    python stream_realsense_data.py data/rosbag/d435i_walk_around.bag

    # Stream data between specific timestamps (seconds from start)
    python stream_realsense_data.py data/rosbag/d435i_walk_around.bag --start 1.0 --end 5.0

    # Stream only specific sensor types
    python stream_realsense_data.py data/rosbag/d435i_walk_around.bag --sensors rgb depth imu

    # Show first N messages
    python stream_realsense_data.py data/rosbag/d435i_walk_around.bag --limit 10
"""

import argparse
import sys
from pathlib import Path
from typing import Iterator, Any
from dataclasses import dataclass
from enum import Enum

from scripts.rosbag_reader import RosbagReader
from scripts.timestamp_handler import (
    ros_timestamp_to_datetime,
    ros_timestamp_to_seconds,
    format_timestamp_iso,
)


class SensorType(Enum):
    """Enumeration of RealSense sensor types."""

    RGB = "rgb"
    DEPTH = "depth"
    IR = "ir"
    ACCEL = "accel"
    GYRO = "gyro"


@dataclass
class SensorMessage:
    """Container for a timestamped sensor message."""

    timestamp_ns: int
    timestamp_sec: float
    sensor_type: SensorType
    topic: str
    msgtype: str
    data: bytes

    def __lt__(self, other: "SensorMessage") -> bool:
        """Compare messages by timestamp for sorting."""
        return self.timestamp_ns < other.timestamp_ns


def classify_topic(topic: str) -> SensorType | None:
    """Classify a topic into a sensor type.

    Args:
        topic: ROS topic name

    Returns:
        SensorType if recognized, None otherwise
    """
    topic_lower = topic.lower()

    if "color" in topic_lower and "image/data" in topic_lower:
        return SensorType.RGB
    elif "depth" in topic_lower and "image/data" in topic_lower:
        return SensorType.DEPTH
    elif "infrared" in topic_lower or "ir_" in topic_lower:
        return SensorType.IR
    elif "accel" in topic_lower and "imu/data" in topic_lower:
        return SensorType.ACCEL
    elif "gyro" in topic_lower and "imu/data" in topic_lower:
        return SensorType.GYRO

    return None


def stream_sensor_data(
    bagfile: Path,
    start_time: float | None = None,
    end_time: float | None = None,
    sensor_types: list[SensorType] | None = None,
    limit: int | None = None,
) -> Iterator[SensorMessage]:
    """Stream sensor data from a ROS bag file in chronological order.

    Args:
        bagfile: Path to the ROS bag file
        start_time: Start time in seconds from bag start (inclusive)
        end_time: End time in seconds from bag start (exclusive)
        sensor_types: List of sensor types to include (None = all)
        limit: Maximum number of messages to yield (None = unlimited)

    Yields:
        SensorMessage objects in chronological order

    Example:
        >>> for msg in stream_sensor_data(Path("data.bag"), start_time=1.0, end_time=5.0):
        ...     print(f"{msg.sensor_type.value}: {msg.timestamp_sec:.3f}")
    """
    with RosbagReader(bagfile) as reader:
        # Get all relevant topics
        all_topics = reader.get_available_topics()

        # Filter topics by sensor type
        selected_topics = []
        for topic in all_topics:
            sensor_type = classify_topic(topic)
            if sensor_type is not None:
                if sensor_types is None or sensor_type in sensor_types:
                    selected_topics.append((topic, sensor_type))

        if not selected_topics:
            return

        # Collect all messages from all topics
        all_messages: list[SensorMessage] = []

        for topic, sensor_type in selected_topics:
            for msg_data in reader.read_messages(topic):
                timestamp_ns = msg_data["timestamp"]
                timestamp_sec = ros_timestamp_to_seconds(timestamp_ns)

                # Apply time filtering
                if start_time is not None and timestamp_sec < start_time:
                    continue
                if end_time is not None and timestamp_sec >= end_time:
                    continue

                sensor_msg = SensorMessage(
                    timestamp_ns=timestamp_ns,
                    timestamp_sec=timestamp_sec,
                    sensor_type=sensor_type,
                    topic=topic,
                    msgtype=msg_data["msgtype"],
                    data=msg_data["data"],
                )
                all_messages.append(sensor_msg)

        # Sort by timestamp
        all_messages.sort()

        # Yield messages (with optional limit)
        count = 0
        for msg in all_messages:
            yield msg
            count += 1
            if limit is not None and count >= limit:
                break


def main() -> int:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Stream RealSense sensor data from ROS bag files with time synchronization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Stream all data
  %(prog)s data/rosbag/d435i_walk_around.bag

  # Stream data between 1 and 5 seconds
  %(prog)s data/rosbag/d435i_walk_around.bag --start 1.0 --end 5.0

  # Stream only RGB and IMU data
  %(prog)s data/rosbag/d435i_walk_around.bag --sensors rgb accel gyro

  # Show first 20 messages
  %(prog)s data/rosbag/d435i_walk_around.bag --limit 20

  # Save to file
  %(prog)s data/rosbag/d435i_walk_around.bag > output.log
        """,
    )

    parser.add_argument(
        "bagfile", type=Path, help="Path to the ROS bag file"
    )

    parser.add_argument(
        "--start",
        "-s",
        type=float,
        help="Start time in seconds from bag start (inclusive)",
        default=None,
    )

    parser.add_argument(
        "--end",
        "-e",
        type=float,
        help="End time in seconds from bag start (exclusive)",
        default=None,
    )

    parser.add_argument(
        "--sensors",
        nargs="+",
        choices=["rgb", "depth", "ir", "accel", "gyro"],
        help="Sensor types to include (default: all)",
        default=None,
    )

    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        help="Maximum number of messages to output",
        default=None,
    )

    parser.add_argument(
        "--format",
        "-f",
        choices=["human", "csv", "json"],
        help="Output format (default: human)",
        default="human",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output (to stderr)",
    )

    args = parser.parse_args()

    # Validate input
    if not args.bagfile.exists():
        print(f"Error: Bag file not found: {args.bagfile}", file=sys.stderr)
        return 1

    if not args.bagfile.is_file():
        print(f"Error: Path is not a file: {args.bagfile}", file=sys.stderr)
        return 1

    # Convert sensor type strings to enums
    sensor_types = None
    if args.sensors:
        sensor_types = [SensorType(s) for s in args.sensors]

    # Verbose output to stderr
    if args.verbose:
        print(f"Opening: {args.bagfile}", file=sys.stderr)
        if args.start is not None:
            print(f"Start time: {args.start:.3f}s", file=sys.stderr)
        if args.end is not None:
            print(f"End time: {args.end:.3f}s", file=sys.stderr)
        if sensor_types:
            print(
                f"Sensors: {', '.join(s.value for s in sensor_types)}",
                file=sys.stderr,
            )
        print(file=sys.stderr)

    # Stream data
    try:
        # Print header
        if args.format == "csv":
            print("timestamp_sec,timestamp_iso,sensor_type,topic,msgtype")
        elif args.format == "json":
            print("[")
            first = True

        count = 0
        for msg in stream_sensor_data(
            args.bagfile,
            start_time=args.start,
            end_time=args.end,
            sensor_types=sensor_types,
            limit=args.limit,
        ):
            count += 1

            if args.format == "human":
                dt = ros_timestamp_to_datetime(msg.timestamp_ns)
                print(
                    f"[{msg.timestamp_sec:10.6f}s] "
                    f"{msg.sensor_type.value:6s} | "
                    f"{format_timestamp_iso(dt)} | "
                    f"{msg.topic}"
                )
            elif args.format == "csv":
                dt = ros_timestamp_to_datetime(msg.timestamp_ns)
                print(
                    f"{msg.timestamp_sec:.6f},"
                    f"{format_timestamp_iso(dt)},"
                    f"{msg.sensor_type.value},"
                    f"{msg.topic},"
                    f"{msg.msgtype}"
                )
            elif args.format == "json":
                import json

                dt = ros_timestamp_to_datetime(msg.timestamp_ns)
                entry = {
                    "timestamp_sec": msg.timestamp_sec,
                    "timestamp_iso": format_timestamp_iso(dt),
                    "sensor_type": msg.sensor_type.value,
                    "topic": msg.topic,
                    "msgtype": msg.msgtype,
                }
                if not first:
                    print(",")
                print(f"  {json.dumps(entry)}", end="")
                first = False

        if args.format == "json":
            print("\n]")

        if args.verbose:
            print(f"\nProcessed {count} messages", file=sys.stderr)

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
