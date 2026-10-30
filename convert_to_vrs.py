#!/usr/bin/env python3
"""Convert RealSense ROSbags with independently selected color/depth image codecs."""

import argparse
import json
import sys
from functools import partial
from pathlib import Path
from typing import Any

from scripts import __version__
from scripts.image_codecs import CodecSpec
from scripts.rosbag_to_vrs_converter import (
    RosbagToVRSConverter,
    create_rgbd_config,
    create_rgbd_imu_config,
)
from scripts.vrs_writer import VRSWriter


def _codec_options(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
        # The value object validates and snapshots primitive JSON options.
        return dict(CodecSpec(options=value).options)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"Codec options must be a JSON object: {exc}") from exc


def main() -> int:
    """Main entry point. Image coding and VRS record compression are independent."""
    parser = argparse.ArgumentParser(
        description="Convert RealSense D435i ROSbag to VRS format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preserve the original raw-image storage (default)
  ./convert_to_vrs.py input.bag output.vrs --imu

  # Lossy color and lossless uint16 depth, with independent VRS record compression
  ./convert_to_vrs.py input.bag output.vrs --imu --color-codec jpeg --depth-codec png --compression zstd

  # Codec-specific options are recorded in the file for automatic restoration
  ./convert_to_vrs.py input.bag output.vrs --color-codec jpeg --color-codec-options '{"quality":90}'

Depth codecs must preserve values. PNG does not support float32 depth; use raw
or register a lossless depth codec through the Python API. See docs/IMAGE_CODECS.md.
        """,
    )
    parser.add_argument("input_bag", type=Path, help="ROS1 .bag file or ROS2 bag directory")
    parser.add_argument("output_vrs", type=Path, help="Output VRS file path")
    parser.add_argument("--imu", "-i", action="store_true", help="Include IMU and device information")
    parser.add_argument(
        "--compression", "-c", choices=["lz4", "zstd", "none"], default="lz4",
        help="VRS record compression, independent of image coding (default: lz4)",
    )
    parser.add_argument(
        "--color-codec", choices=["raw", "png", "jpeg"], default="raw",
        help="Color image codec (default: raw; JPEG is lossy)",
    )
    parser.add_argument(
        "--depth-codec", choices=["raw", "png"], default="raw",
        help="Lossless depth image codec (default: raw)",
    )
    for role in ("color", "depth"):
        parser.add_argument(
            f"--{role}-codec-options", type=_codec_options, default={}, metavar="JSON",
            help="JSON options: JPEG quality 1..100; PNG compression_level 0..9; raw has no options",
        )
    parser.add_argument("--verbose", "-v", action="store_true", help="Detailed progress information")
    parser.add_argument(
        "--version", action="version",
        version=f"%(prog)s {__version__} (official VRS writer, schemas 2/3)",
    )
    args = parser.parse_args()
    if not args.input_bag.exists():
        print(f"Error: Input ROSbag not found: {args.input_bag}", file=sys.stderr)
        return 1

    try:
        args.output_vrs.parent.mkdir(parents=True, exist_ok=True)
        config_factory = create_rgbd_imu_config if args.imu else create_rgbd_config
        config = config_factory(compression=args.compression, verbose=args.verbose)
        choices = {
            "color": CodecSpec(args.color_codec, options=args.color_codec_options),
            "depth": CodecSpec(args.depth_codec, options=args.depth_codec_options),
        }
        # The conversion layer remains codec-agnostic; its existing factory is
        # the composition point. No hard-coded stream numbers are needed here.
        writer_factory = partial(
            VRSWriter,
            compression=args.compression,
            image_codecs={
                stream.stream_id: choices[stream.stream_type]
                for stream in config.topic_mapping.values()
                if stream.stream_type in choices
            },
        )
        converter = RosbagToVRSConverter(
            args.input_bag, args.output_vrs, config, writer_factory=writer_factory
        )
        if args.verbose:
            print(f"Input: {args.input_bag}")
            print(f"Output: {args.output_vrs}")
            print(f"Record compression: {args.compression}")
            print(f"Color codec: {args.color_codec}; depth codec: {args.depth_codec}")
        result = converter.convert()
        print("Conversion Complete!")
        print(f"  Input size:       {result.input_bag_size / 1024 / 1024:.2f} MB")
        print(f"  Output size:      {result.output_vrs_size / 1024 / 1024:.2f} MB")
        print(f"  Compression:      {result.compression_ratio:.2%}")
        print(f"  Total messages:   {result.total_messages}")
        print(f"  - Color stream:   {result.messages_per_stream.get(1001, 0)} records")
        print(f"  - Depth stream:   {result.messages_per_stream.get(1002, 0)} records")
        print(f"  Conversion time:  {result.conversion_time_sec:.2f}s")
        print(f"  Bag duration:     {result.duration_sec:.2f}s")
        print(f"  Output file:      {args.output_vrs}")
        return 0
    except KeyboardInterrupt:
        print("Conversion cancelled by user.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Conversion Failed: {exc}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
