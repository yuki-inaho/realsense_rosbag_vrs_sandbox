#!/usr/bin/env python3
"""
CLI tool for converting RealSense D435i ROSbag files to VRS format.

Phase 4A: Color + Depth streams (必須)

Usage:
    python scripts/convert_rosbag_to_vrs.py input.bag output.vrs
    python scripts/convert_rosbag_to_vrs.py input.bag output.vrs --verbose
"""
import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.rosbag_to_vrs_converter import (  # noqa: E402
    RosbagToVRSConverter,
    create_phase_4a_config,
)


def main() -> int:
    """Main entry point for ROSbag to VRS conversion CLI"""
    parser = argparse.ArgumentParser(
        description="Convert RealSense D435i ROSbag to VRS format (Phase 4A: Color + Depth)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert ROSbag to VRS
  python scripts/convert_rosbag_to_vrs.py data/rosbag/sample.bag output.vrs

  # Convert with verbose output
  python scripts/convert_rosbag_to_vrs.py data/rosbag/sample.bag output.vrs --verbose

  # Specify compression (lz4 or zstd)
  python scripts/convert_rosbag_to_vrs.py data/rosbag/sample.bag output.vrs --compression zstd

Phase 4A streams:
  - Stream 1001: Color Image (RGB, 1920x1080)
  - Stream 1002: Depth Image (16UC1, 1280x720)

Note: Phase 4B (IMU) and Phase 4C (TF, metadata) are not yet implemented.
        """,
    )

    parser.add_argument(
        "input_bag",
        type=Path,
        help="Input ROSbag file path (.bag for ROS1, directory for ROS2)",
    )

    parser.add_argument(
        "output_vrs",
        type=Path,
        help="Output VRS file path (.vrs extension recommended)",
    )

    parser.add_argument(
        "--compression",
        choices=["lz4", "zstd", "none"],
        default="lz4",
        help="Compression algorithm (default: lz4)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Validate input
    if not args.input_bag.exists():
        print(f"Error: Input ROSbag file not found: {args.input_bag}", file=sys.stderr)
        return 1

    # Create output directory if needed
    output_dir = args.output_vrs.parent
    if output_dir and not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
        if args.verbose:
            print(f"Created output directory: {output_dir}")

    # Create converter configuration
    config = create_phase_4a_config(
        compression=args.compression,
        verbose=args.verbose,
    )

    # Run conversion
    try:
        converter = RosbagToVRSConverter(
            args.input_bag,
            args.output_vrs,
            config,
        )

        if args.verbose:
            print(f"Converting {args.input_bag} -> {args.output_vrs}")
            print(f"Configuration: Phase 4A (Color + Depth)")
            print(f"Compression: {args.compression}")
            print("-" * 60)

        result = converter.convert()

        # Print summary
        print(f"\nConversion complete!")
        print(f"  Input:  {result.input_bag_size / 1024 / 1024:.2f} MB")
        print(f"  Output: {result.output_vrs_size / 1024 / 1024:.2f} MB")
        print(f"  Compression ratio: {result.compression_ratio:.2%}")
        print(f"  Total messages: {result.total_messages}")
        print(f"  Conversion time: {result.conversion_time_sec:.2f}s")
        print(f"  Bag duration: {result.duration_sec:.2f}s")
        print(f"\nOutput file: {args.output_vrs}")

        return 0

    except Exception as e:
        print(f"Error: Conversion failed: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
