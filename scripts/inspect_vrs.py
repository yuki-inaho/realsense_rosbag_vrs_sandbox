#!/usr/bin/env python3
"""
VRS File Inspector

Display VRS file contents: streams, configurations, record counts.

Usage:
    python scripts/inspect_vrs.py file.vrs
    python scripts/inspect_vrs.py file.vrs --verbose
"""
import sys
import argparse
from pathlib import Path
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.vrs_reader import VRSReader  # noqa: E402


def main() -> int:
    """Main entry point for VRS inspector CLI"""
    parser = argparse.ArgumentParser(
        description="Inspect VRS file contents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Inspect VRS file
  python scripts/inspect_vrs.py output.vrs

  # Show detailed information
  python scripts/inspect_vrs.py output.vrs --verbose
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
        help="Show detailed information including configuration data",
    )

    args = parser.parse_args()

    # Validate input
    if not args.vrs_file.exists():
        print(f"Error: VRS file not found: {args.vrs_file}", file=sys.stderr)
        return 1

    # Inspect VRS file
    try:
        with VRSReader(args.vrs_file) as reader:
            print(f"VRS File: {args.vrs_file}")
            print(f"Size: {args.vrs_file.stat().st_size / 1024 / 1024:.2f} MB")
            print("=" * 70)

            # Get stream IDs
            stream_ids = reader.get_stream_ids()
            print(f"\nTotal Streams: {len(stream_ids)}")
            print("-" * 70)

            # Iterate through streams
            for stream_id in stream_ids:
                print(f"\nStream ID: {stream_id}")

                # Get record count
                record_count = reader.get_record_count(stream_id)
                print(f"  Total Records: {record_count}")

                # Get configuration
                try:
                    config = reader.read_configuration(stream_id)
                    if config:
                        print(f"  Configuration:")
                        if args.verbose:
                            # Pretty print full configuration
                            for key, value in config.items():
                                if isinstance(value, (list, tuple)) and len(value) > 5:
                                    # Truncate long arrays
                                    print(f"    {key}: [{value[0]}, {value[1]}, ..., {value[-1]}] ({len(value)} elements)")
                                else:
                                    print(f"    {key}: {value}")
                        else:
                            # Show only key information
                            if "width" in config and "height" in config:
                                print(f"    Resolution: {config['width']}x{config['height']}")
                            if "encoding" in config:
                                print(f"    Encoding: {config['encoding']}")
                            if "frame_id" in config:
                                print(f"    Frame ID: {config['frame_id']}")
                            if "depth_scale" in config:
                                print(f"    Depth Scale: {config['depth_scale']}")
                except Exception as e:
                    print(f"  Configuration: Error reading - {e}")

                # Sample data records (first and last)
                if record_count > 0:
                    try:
                        data_records = reader.read_data_records(stream_id)
                        if data_records:
                            first_record = data_records[0]
                            last_record = data_records[-1]

                            print(f"  Data Records:")
                            print(f"    First timestamp: {first_record.get('timestamp', 'N/A')}")
                            print(f"    Last timestamp: {last_record.get('timestamp', 'N/A')}")

                            if args.verbose and "data" in first_record:
                                data_size = len(first_record["data"]) if isinstance(first_record["data"], (bytes, list)) else 0
                                print(f"    Data size (first record): {data_size} bytes")

                    except Exception as e:
                        print(f"  Data Records: Error reading - {e}")

            print("\n" + "=" * 70)
            print("Inspection complete.")

        return 0

    except Exception as e:
        print(f"Error: Failed to inspect VRS file: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
