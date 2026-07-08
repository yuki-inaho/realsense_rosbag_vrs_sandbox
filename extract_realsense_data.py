#!/usr/bin/env python3
"""Extract RealSense RGB-D-IR and IMU data from ROS bag files with timestamps.

This script reads ROS bag files containing RealSense camera data and extracts
information about the recorded streams, including timestamps, message counts,
and topic information.

Usage:
    python extract_realsense_data.py <bagfile_path>
    python extract_realsense_data.py data/rosbag/d435i_walk_around.bag
"""

import argparse
import sys
from pathlib import Path

from scripts.rosbag_reader import RosbagReader
from scripts.timestamp_handler import format_timestamp_iso, ros_timestamp_to_datetime


def main() -> int:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Extract RealSense data from ROS bag files with timestamps"
    )
    parser.add_argument("bagfile", type=Path, help="Path to the ROS bag file")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output directory for extracted data (default: current directory)",
        default=Path("."),
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Validate input
    if not args.bagfile.exists():
        print(f"Error: Bag file not found: {args.bagfile}", file=sys.stderr)
        return 1

    if not args.bagfile.is_file():
        print(f"Error: Path is not a file: {args.bagfile}", file=sys.stderr)
        return 1

    # Extract data
    try:
        extract_realsense_data(args.bagfile, args.output, args.verbose)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


def extract_realsense_data(bagfile: Path, output_dir: Path, verbose: bool = False) -> None:
    """Extract RealSense data from a ROS bag file.

    Args:
        bagfile: Path to the ROS bag file
        output_dir: Directory to save extracted data
        verbose: Enable verbose output
    """
    print(f"Opening ROS bag: {bagfile}")

    with RosbagReader(bagfile) as reader:
        # Get bag file information
        duration = reader.get_duration()
        topics_info = reader.get_topics_info()

        print(f"Bag duration: {duration:.2f} seconds")
        print(f"Total topics: {len(topics_info)}")
        print()

        # Filter RealSense topics
        image_topics = reader.filter_topics("image/data")
        imu_topics = reader.filter_topics("imu/data")

        print("RealSense Image Topics:")
        for topic in image_topics:
            info = topics_info[topic]
            print(f"  {topic}")
            print(f"    Type: {info['msgtype']}")
            print(f"    Messages: {info['msgcount']}")

            if verbose and info["msgcount"] > 0:
                # Show first and last message timestamps
                messages = list(reader.read_messages(topic))
                if messages:
                    first_msg = messages[0]
                    last_msg = messages[-1]

                    first_time = ros_timestamp_to_datetime(first_msg["timestamp"])
                    last_time = ros_timestamp_to_datetime(last_msg["timestamp"])

                    print(f"    First message: {format_timestamp_iso(first_time)}")
                    print(f"    Last message:  {format_timestamp_iso(last_time)}")
        print()

        print("RealSense IMU Topics:")
        for topic in imu_topics:
            info = topics_info[topic]
            print(f"  {topic}")
            print(f"    Type: {info['msgtype']}")
            print(f"    Messages: {info['msgcount']}")

            if verbose and info["msgcount"] > 0:
                # Show first and last message timestamps
                messages = list(reader.read_messages(topic))
                if messages:
                    first_msg = messages[0]
                    last_msg = messages[-1]

                    first_time = ros_timestamp_to_datetime(first_msg["timestamp"])
                    last_time = ros_timestamp_to_datetime(last_msg["timestamp"])

                    print(f"    First message: {format_timestamp_iso(first_time)}")
                    print(f"    Last message:  {format_timestamp_iso(last_time)}")
        print()

        # Summary
        total_image_messages = sum(topics_info[topic]["msgcount"] for topic in image_topics)
        total_imu_messages = sum(topics_info[topic]["msgcount"] for topic in imu_topics)

        print("Summary:")
        print(f"  Image topics: {len(image_topics)} ({total_image_messages} messages)")
        print(f"  IMU topics: {len(imu_topics)} ({total_imu_messages} messages)")
        print(f"  Total data messages: {total_image_messages + total_imu_messages}")


if __name__ == "__main__":
    sys.exit(main())
