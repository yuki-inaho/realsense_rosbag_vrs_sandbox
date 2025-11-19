# vrs_sandbox

RealSense ROS bag data extraction tool for RGB-D-IR and IMU data with timestamps.

## Setup

### Install dependencies

```bash
uv sync --all-extras
```

### Git LFS & ROSBag Setup

Your recorded ROSbag file:

```bash
git lfs install
git lfs pull
```

### Download Intel RealSense Sample Data

For testing and development, you can download official Intel RealSense D435i sample datasets:

```bash
# Download sample data (451MB zip file)
wget https://librealsense.intel.com/rs-tests/TestData/d435i_sample_data.zip

# Extract
unzip d435i_sample_data.zip

# Copy to project (recommended: outdoor scene with IMU data)
cp d435i_walk_around.bag data/rosbag/
```

Available sample files:
- `d435i_walk_around.bag` (803MB) - Outdoor scene with D435i (Depth + RGB + IMU) - Primary test file
- `d435i_walking.bag` (690MB) - Walking scene with D435i (Depth + RGB + IMU)

Source: [IntelRealSense/librealsense Sample Data](https://github.com/IntelRealSense/librealsense/blob/master/doc/sample-data.md)

## Usage

### Extract bag information

Display information about topics and message counts:

```bash
# Basic information
uv run python extract_realsense_data.py data/rosbag/d435i_walk_around.bag

# Verbose mode with timestamps
uv run python extract_realsense_data.py data/rosbag/d435i_walk_around.bag --verbose
```

### Stream synchronized sensor data

Stream RGB-D-IR and IMU data in chronological order:

```bash
# Stream all sensor data
uv run python stream_realsense_data.py data/rosbag/d435i_walk_around.bag

# Stream data between specific times (seconds from start)
uv run python stream_realsense_data.py data/rosbag/d435i_walk_around.bag --start 1.0 --end 5.0

# Stream only specific sensors (rgb, depth, ir, accel, gyro)
uv run python stream_realsense_data.py data/rosbag/d435i_walk_around.bag --sensors rgb depth

# Show first N messages
uv run python stream_realsense_data.py data/rosbag/d435i_walk_around.bag --limit 20

# Output in CSV format
uv run python stream_realsense_data.py data/rosbag/d435i_walk_around.bag --format csv > output.csv

# Output in JSON format
uv run python stream_realsense_data.py data/rosbag/d435i_walk_around.bag --format json > output.json

# Combine filters
uv run python stream_realsense_data.py data/rosbag/d435i_walk_around.bag \
  --start 2.0 --end 8.0 --sensors rgb depth accel gyro --format csv
```

**Output formats:**
- `human` (default): Human-readable format with timestamps
- `csv`: CSV format with headers
- `json`: JSON array format

## Development

### pyvrs_writer C++ Extension Dependencies

For building the `pyvrs_writer` C++ extension (VRS file writing support):

```bash
# Install C++ build dependencies (Ubuntu/Debian)
apt-get install -y \
  libboost-all-dev \
  libfmt-dev \
  liblz4-dev \
  libzstd-dev \
  libxxhash-dev \
  ninja-build \
  libjpeg-dev \
  libturbojpeg-dev \
  libpng-dev \
  libeigen3-dev \
  libgtest-dev \
  googletest \
  pybind11-dev
```

Build VRS library locally:

```bash
# Build VRS from submodule
cd third/vrs
mkdir -p build
cd build
cmake -S .. -B . -G Ninja \
  -DCMAKE_INSTALL_PREFIX=/home/user/realsense_vrs_sandbox/third/vrs_install \
  -DCMAKE_BUILD_TYPE=Release
ninja
ninja install
```

### Run tests

```bash
uv run pytest
```

### Run linter

```bash
uv run ruff check scripts/ tests/
```

### Type checking

```bash
uv run mypy scripts/
```
