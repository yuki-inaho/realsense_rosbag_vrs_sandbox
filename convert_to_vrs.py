#!/usr/bin/env python3
"""
RealSense ROSbag to VRS Converter

Convert RealSense D435i ROSbag files to VRS (Virtual Reality Stream) format.
Supports Color and Depth streams with camera calibration parameters.

Usage:
    ./convert_to_vrs.py input.bag output.vrs
    ./convert_to_vrs.py input.bag output.vrs --verbose
    ./convert_to_vrs.py input.bag output.vrs --compression zstd
"""
import sys
import argparse
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from rosbag_to_vrs_converter import (  # noqa: E402
    RosbagToVRSConverter,
    create_rgbd_config,
    create_rgbd_imu_config,
)


def main() -> int:
    """Main entry point for ROSbag to VRS conversion"""
    parser = argparse.ArgumentParser(
        description="Convert RealSense D435i ROSbag to VRS format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert ROSbag to VRS
  ./convert_to_vrs.py data/rosbag/sample.bag output.vrs

  # Convert with verbose output
  ./convert_to_vrs.py data/rosbag/sample.bag output.vrs --verbose

  # Specify compression algorithm (lz4, zstd, or none)
  ./convert_to_vrs.py data/rosbag/sample.bag output.vrs --compression zstd

Supported Data:
  - Color Image: RGB camera stream with intrinsic parameters
  - Depth Image: Depth camera stream with intrinsic parameters and depth scale
  - Transform: Camera extrinsic parameters (included by default)
  - IMU Data: Accelerometer and Gyroscope (optional, use --imu)
  - Camera Info: K matrix, distortion coefficients, distortion model

Features:
  - Automatic ROS1/ROS2 bag detection
  - LZ4/ZSTD compression support
  - Camera calibration parameter preservation
  - Progress reporting and statistics
        """,
    )

    parser.add_argument(
        "input_bag",
        type=Path,
        help="Input ROSbag file (.bag for ROS1, directory for ROS2)",
    )

    parser.add_argument(
        "output_vrs",
        type=Path,
        help="Output VRS file path (.vrs extension)",
    )

    parser.add_argument(
        "--imu",
        "-i",
        action="store_true",
        help="Include IMU streams (Accelerometer and Gyroscope)",
    )

    parser.add_argument(
        "--compression",
        "-c",
        choices=["lz4", "zstd", "none"],
        default="lz4",
        help="Compression algorithm (default: lz4)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output with detailed progress information",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0 (RGB-D + IMU + Transform support)",
    )

    args = parser.parse_args()

    # Validate input
    if not args.input_bag.exists():
        print(f"Error: Input ROSbag not found: {args.input_bag}", file=sys.stderr)
        print(f"\nTip: Check the file path and ensure the bag file exists.", file=sys.stderr)
        return 1

    # Create output directory if needed
    output_dir = args.output_vrs.parent
    if output_dir and not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
        if args.verbose:
            print(f"Created output directory: {output_dir}")

    # Create converter configuration
    if args.imu:
        config = create_rgbd_imu_config(
            compression=args.compression,
            verbose=args.verbose,
        )
    else:
        config = create_rgbd_config(
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
            print("="*70)
            print(f"🔄 Converting ROSbag to VRS")
            print("="*70)
            print(f"  Input:       {args.input_bag}")
            print(f"  Output:      {args.output_vrs}")
            print(f"  Compression: {args.compression}")
            print(f"  Phase:       4A (Color + Depth)")
            print("-" * 70)

        result = converter.convert()

        # Print summary
        print(f"\n{'='*70}")
        print(f"✅ Conversion Complete!")
        print(f"{'='*70}")
        print(f"  Input size:       {result.input_bag_size / 1024 / 1024:.2f} MB")
        print(f"  Output size:      {result.output_vrs_size / 1024 / 1024:.2f} MB")
        print(f"  Compression:      {result.compression_ratio:.2%}")
        print(f"  Total messages:   {result.total_messages}")
        print(f"  - Color stream:   {result.messages_per_stream.get(1001, 0)} records")
        print(f"  - Depth stream:   {result.messages_per_stream.get(1002, 0)} records")
        print(f"  Conversion time:  {result.conversion_time_sec:.2f}s")
        print(f"  Bag duration:     {result.duration_sec:.2f}s")
        print(f"\n📄 Output file: {args.output_vrs}")
        print(f"\nTo inspect the VRS file, run:")
        print(f"  ./inspect_vrs.py {args.output_vrs}")

        return 0

    except KeyboardInterrupt:
        print(f"\n\n⚠️  Conversion cancelled by user.", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"\n{'='*70}", file=sys.stderr)
        print(f"❌ Conversion Failed", file=sys.stderr)
        print(f"{'='*70}", file=sys.stderr)
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            print(f"\nDetailed traceback:", file=sys.stderr)
            import traceback
            traceback.print_exc()
        else:
            print(f"\nTip: Run with --verbose for detailed error information.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
