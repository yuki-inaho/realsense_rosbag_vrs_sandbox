# pyvrs_writer

Python bindings for VRS (Virtual Reality Stream) file writing.

## Overview

This package provides Python interface to write VRS files using the VRS C++ library.
PyVRS (official package) only supports reading VRS files, so this package fills that gap.

## Installation

### Prerequisites

- Python 3.9+
- CMake 3.10+
- C++17 compiler
- VRS C++ library dependencies: boost, lz4, zstd, fmt

### Build and Install

```bash
cd pyvrs_writer
pip install -e .
```

## Usage

### Basic Example

```python
from pyvrs_writer import VRSWriter

with VRSWriter("output.vrs") as writer:
    # Add a stream
    writer.add_stream(1001, "RGB Camera")

    # Write configuration
    config = '{"width": 640, "height": 480}'
    writer.write_configuration(1001, config)

    # Write data (use list of integers, not bytes)
    data = [0x01, 0x02, 0x03]
    writer.write_data(1001, 0.0, data)
```

## API Reference

### VRSWriter

#### `__init__(filepath: str)`
Create a new VRS file.

#### `add_stream(stream_id: int, stream_name: str)`
Add a new stream to the VRS file.

#### `write_configuration(stream_id: int, json_config: str)`
Write a configuration record.

#### `write_data(stream_id: int, timestamp: float, data: List[int])`
Write a data record.

**Parameters:**
- `stream_id`: Stream ID (int)
- `timestamp`: Timestamp in seconds (float)
- `data`: Data as a list of integers (List[int])

#### `close()`
Close the VRS file.

#### `is_open() -> bool`
Check if the file is open.

## Testing

```bash
# C++ tests
cd build
ctest --output-on-failure

# Python tests
pytest python_tests/ -v
```

## License

Apache 2.0 (same as VRS C++ library)
