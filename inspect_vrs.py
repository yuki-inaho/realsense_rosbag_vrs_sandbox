#!/usr/bin/env python3
"""
VRS File Inspector

Inspect VRS (Virtual Reality Stream) files and display detailed information
about streams, configurations, camera parameters, and record counts.

Usage:
    ./inspect_vrs.py file.vrs
    ./inspect_vrs.py file.vrs --verbose
    ./inspect_vrs.py file.vrs --stream 1001
"""
import sys
import argparse
from pathlib import Path
import json

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from vrs_reader import VRSReader  # noqa: E402


def format_camera_matrix(matrix: list, name: str = "K") -> str:
    """Format 3x3 camera matrix for display"""
    if len(matrix) != 9:
        return str(matrix)

    lines = []
    lines.append(f"    {name} matrix (3x3):")
    for i in range(3):
        row = matrix[i*3:(i+1)*3]
        lines.append(f"      [{row[0]:>10.4f}, {row[1]:>10.4f}, {row[2]:>10.4f}]")
    return "\n".join(lines)


def main() -> int:
    """Main entry point for VRS inspector"""
    parser = argparse.ArgumentParser(
        description="Inspect VRS file contents and display stream information",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Inspect all streams in VRS file
  ./inspect_vrs.py output.vrs

  # Show detailed information (camera matrices, distortion coefficients)
  ./inspect_vrs.py output.vrs --verbose

  # Inspect specific stream
  ./inspect_vrs.py output.vrs --stream 1001

  # Export configuration as JSON
  ./inspect_vrs.py output.vrs --json > config.json

Stream Information:
  - Stream IDs and record counts
  - Camera intrinsic parameters (K matrix)
  - Distortion coefficients (D vector)
  - Image resolution and encoding
  - Depth scale (for depth streams)
  - Timestamp ranges

Tip: This tool provides ROSbag-equivalent information display.
        """,
    )

    parser.add_argument(
        "vrs_file",
        type=Path,
        help="VRS file path to inspect",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed information including full camera matrices",
    )

    parser.add_argument(
        "--stream",
        "-s",
        type=int,
        help="Inspect specific stream ID only",
    )

    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output configuration as JSON format",
    )

    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )

    args = parser.parse_args()

    # Validate input
    if not args.vrs_file.exists():
        print(f"Error: VRS file not found: {args.vrs_file}", file=sys.stderr)
        print(f"\nTip: Check the file path and ensure the VRS file exists.", file=sys.stderr)
        return 1

    # Inspect VRS file
    try:
        with VRSReader(args.vrs_file) as reader:
            # Get stream IDs
            stream_ids = reader.get_stream_ids()

            # Filter by specific stream if requested
            if args.stream is not None:
                if args.stream not in stream_ids:
                    print(f"Error: Stream {args.stream} not found in VRS file.", file=sys.stderr)
                    print(f"Available streams: {stream_ids}", file=sys.stderr)
                    return 1
                stream_ids = [args.stream]

            # JSON output mode
            if args.json:
                output = {
                    "file": str(args.vrs_file),
                    "size_mb": args.vrs_file.stat().st_size / 1024 / 1024,
                    "streams": {}
                }

                for stream_id in stream_ids:
                    config = reader.read_configuration(stream_id)
                    record_count = reader.get_record_count(stream_id)
                    output["streams"][stream_id] = {
                        "record_count": record_count,
                        "configuration": config
                    }

                print(json.dumps(output, indent=2))
                return 0

            # Human-readable output
            print("="*70)
            print(f"📄 VRS File Inspection")
            print("="*70)
            print(f"  File:         {args.vrs_file.name}")
            print(f"  Path:         {args.vrs_file}")
            print(f"  Size:         {args.vrs_file.stat().st_size / 1024 / 1024:.2f} MB")
            print(f"  Total Streams: {len(stream_ids)}")

            # Iterate through streams
            for idx, stream_id in enumerate(stream_ids, 1):
                print(f"\n{'='*70}")
                print(f"Stream {idx}/{len(stream_ids)}: ID {stream_id}")
                print("="*70)

                # Get record count
                record_count = reader.get_record_count(stream_id)
                print(f"  📊 Record Count: {record_count}")

                # Get configuration
                try:
                    config = reader.read_configuration(stream_id)
                    if config:
                        print(f"\n  ⚙️  Configuration:")

                        # Resolution
                        if "width" in config and "height" in config:
                            print(f"    Resolution:   {config['width']}x{config['height']}")

                        # Encoding
                        if "encoding" in config:
                            print(f"    Encoding:     {config['encoding']}")

                        # Frame ID
                        if "frame_id" in config:
                            frame_id = config['frame_id'] if config['frame_id'] else "(empty)"
                            print(f"    Frame ID:     {frame_id}")

                        # Depth scale (for depth streams)
                        if "depth_scale" in config:
                            print(f"    Depth Scale:  {config['depth_scale']} (depth units to meters)")

                        # Camera intrinsic parameters
                        if "camera_k" in config:
                            if args.verbose:
                                print(f"\n  📷 Camera Intrinsic Parameters:")
                                print(format_camera_matrix(config['camera_k'], "K"))
                            else:
                                k = config['camera_k']
                                fx, fy = k[0], k[4]
                                cx, cy = k[2], k[5]
                                print(f"\n  📷 Camera Intrinsics:")
                                print(f"    fx: {fx:.2f}, fy: {fy:.2f}")
                                print(f"    cx: {cx:.2f}, cy: {cy:.2f}")

                        # Distortion parameters
                        if "camera_d" in config:
                            d = config['camera_d']
                            if args.verbose:
                                print(f"\n    D (distortion): {d}")
                            else:
                                print(f"    Distortion:   [{d[0]:.6f}, {d[1]:.6f}, {d[2]:.6f}, {d[3]:.6f}, {d[4]:.6f}]")

                        # Distortion model
                        if "distortion_model" in config:
                            print(f"    Model:        {config['distortion_model']}")

                        # Verbose mode: show all other fields
                        if args.verbose:
                            other_fields = {k: v for k, v in config.items()
                                          if k not in ["width", "height", "encoding", "frame_id",
                                                      "depth_scale", "camera_k", "camera_d", "distortion_model"]}
                            if other_fields:
                                print(f"\n  🔧 Other Configuration:")
                                for key, value in other_fields.items():
                                    print(f"    {key}: {value}")
                except Exception as e:
                    print(f"  ⚠️  Configuration: Error reading - {e}")

                # Sample data records (first and last timestamps)
                if record_count > 0:
                    try:
                        data_records = reader.read_data_records(stream_id)
                        if data_records:
                            # Note: data_records is a generator, need to handle carefully
                            records_list = list(data_records)
                            if records_list:
                                first_record = records_list[0]
                                last_record = records_list[-1]

                                print(f"\n  ⏱️  Timestamp Range:")
                                print(f"    First: {first_record.get('timestamp', 'N/A')}")
                                print(f"    Last:  {last_record.get('timestamp', 'N/A')}")

                                if args.verbose and "data" in first_record:
                                    data_size = len(first_record["data"]) if isinstance(first_record["data"], (bytes, list)) else 0
                                    print(f"\n  💾 Data Size:")
                                    print(f"    First record: {data_size:,} bytes")
                                    if data_size > 0:
                                        print(f"    Estimated total: {data_size * record_count / 1024 / 1024:.2f} MB")

                    except Exception as e:
                        # Generator error is expected with current implementation
                        if "generator" not in str(e).lower():
                            print(f"  ⚠️  Data Records: Error reading - {e}")

            print(f"\n{'='*70}")
            print("✅ Inspection complete.")
            print(f"\nTip: Use --verbose for detailed camera matrices and parameters.")

        return 0

    except KeyboardInterrupt:
        print(f"\n\n⚠️  Inspection cancelled by user.", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"\n{'='*70}", file=sys.stderr)
        print(f"❌ Inspection Failed", file=sys.stderr)
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
