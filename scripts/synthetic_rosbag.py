"""Generate deterministic RealSense-shaped ROS1 bags without recorded data.

The fixture contains RGB8 and 16UC1 images, accelerometer/gyroscope samples,
camera calibration, transforms, device/sensor information and options.  Data
are generated from coordinates and frame numbers; no device or external file
is accessed.  Files are deliberately generated on demand rather than stored
in the repository.

Run ``python -m scripts.synthetic_rosbag output.bag --frames 4`` to create a
small 640 x 480 fixture.  Use ``SyntheticBagSpec`` for smaller unit fixtures or
longer recordings that exercise periodic VRS flushing.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from rosbags.rosbag1 import Writer, WriterError
from rosbags.typesys import Stores, get_types_from_msg, get_typestore

COLOR_TOPIC = "/device_0/sensor_1/Color_0/image/data"
DEPTH_TOPIC = "/device_0/sensor_0/Depth_0/image/data"
ACCEL_TOPIC = "/device_0/sensor_2/Accel_0/imu/data"
GYRO_TOPIC = "/device_0/sensor_2/Gyro_0/imu/data"

_STREAM_INFO_TYPE = "realsense2_camera_msgs/msg/StreamInfo"
_STREAM_INFO_DEFINITION = "uint32 fps\nstring encoding\nbool is_recommended\n"


@dataclass(frozen=True)
class SyntheticBagSpec:
    """Parameters for reproducible data, including image-layout edge cases.

    Color and depth share each frame's bag timestamp.  Accelerometer and
    gyroscope records follow at +1 ms and +2 ms.  Static metadata precede the
    first frame by 1 ms.  ``depth_scale`` is metres per depth unit.
    """

    width: int = 640
    height: int = 480
    frame_count: int = 4
    frame_period_ns: int = 40_000_000
    start_time_ns: int = 10_000_000_000
    depth_scale: float = 0.002
    row_padding_bytes: int = 0
    depth_bigendian: bool = False

    def __post_init__(self) -> None:
        for name in ("width", "height", "frame_count", "frame_period_ns", "start_time_ns"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.start_time_ns < 1_000_000:
            raise ValueError("start_time_ns must allow 1 ms of preceding metadata")
        if self.frame_period_ns <= 2_000_000:
            raise ValueError("frame_period_ns must exceed the 2 ms IMU offset")
        if (
            isinstance(self.row_padding_bytes, bool)
            or not isinstance(self.row_padding_bytes, int)
            or self.row_padding_bytes < 0
        ):
            raise ValueError("row_padding_bytes must be a non-negative integer")
        if not math.isfinite(self.depth_scale) or self.depth_scale <= 0:
            raise ValueError("depth_scale must be finite and positive")
        last_timestamp = (
            self.start_time_ns + (self.frame_count - 1) * self.frame_period_ns + 2_000_000
        )
        if last_timestamp >= (2**32) * 1_000_000_000:
            raise ValueError("timestamps exceed the ROS1 Time range")


class _MessageFactory:
    """Construct messages from the type definitions embedded in the bag."""

    def __init__(self, spec: SyntheticBagSpec) -> None:
        self.spec = spec
        self.typestore = get_typestore(Stores.ROS1_NOETIC)
        self.typestore.register(get_types_from_msg(_STREAM_INFO_DEFINITION, _STREAM_INFO_TYPE))

    def message(self, msgtype: str, **fields: Any) -> Any:
        return self.typestore.types[msgtype](**fields)

    def header(self, timestamp_ns: int, index: int, frame_id: str) -> Any:
        seconds, nanoseconds = divmod(timestamp_ns, 1_000_000_000)
        stamp = self.message("builtin_interfaces/msg/Time", sec=seconds, nanosec=nanoseconds)
        return self.message("std_msgs/msg/Header", seq=index, stamp=stamp, frame_id=frame_id)

    def vector(self, values: tuple[float, float, float]) -> Any:
        return self.message("geometry_msgs/msg/Vector3", x=values[0], y=values[1], z=values[2])

    def quaternion(self, values: tuple[float, float, float, float]) -> Any:
        return self.message(
            "geometry_msgs/msg/Quaternion",
            x=values[0],
            y=values[1],
            z=values[2],
            w=values[3],
        )

    def camera_info(self, *, depth: bool) -> Any:
        spec = self.spec
        fx = 580.0 if depth else 520.0
        fy = fx + 1.0
        cx, cy = (spec.width - 1) / 2, (spec.height - 1) / 2
        fields = {
            "header": self.header(
                spec.start_time_ns - 1_000_000,
                0,
                "synthetic_depth_optical_frame" if depth else "synthetic_color_optical_frame",
            ),
            "height": spec.height,
            "width": spec.width,
            "distortion_model": "plumb_bob",
            "D": np.array([0.1, -0.01, 0.001, -0.002, 0.0003], dtype=np.float64),
            "K": np.array([fx, 0.0, cx, 0.0, fy, cy, 0.0, 0.0, 1.0], dtype=np.float64),
            "R": np.eye(3, dtype=np.float64).reshape(-1),
            "P": np.array(
                [fx, 0.0, cx, 0.0, 0.0, fy, cy, 0.0, 0.0, 0.0, 1.0, 0.0], dtype=np.float64
            ),
            "binning_x": 0,
            "binning_y": 0,
            "roi": self.message(
                "sensor_msgs/msg/RegionOfInterest",
                x_offset=0,
                y_offset=0,
                height=spec.height,
                width=spec.width,
                do_rectify=False,
            ),
        }
        return self.message("sensor_msgs/msg/CameraInfo", **fields)

    def image(self, index: int, timestamp_ns: int, *, depth: bool) -> Any:
        spec = self.spec
        y, x = np.indices((spec.height, spec.width), dtype=np.uint32)
        if depth:
            # Distinct values exercise 16-bit range, zeros and maximum depth.
            pixels = ((31 * x + 17 * y + 101 * index) % 65_536).astype(np.uint16)
            pixels[0, 0] = 0
            pixels[-1, -1] = 65_535
            pixels = pixels.astype(">u2" if spec.depth_bigendian else "<u2")
            encoding, packed_row_bytes = "16UC1", spec.width * 2
        else:
            pixels = np.stack(
                ((x + 7 * index) % 256, (y + 11 * index) % 256, (x + y + 13 * index) % 256),
                axis=-1,
            ).astype(np.uint8)
            encoding, packed_row_bytes = "rgb8", spec.width * 3
        step = packed_row_bytes + spec.row_padding_bytes
        rows = np.full((spec.height, step), 0xA5, dtype=np.uint8)
        rows[:, :packed_row_bytes] = np.frombuffer(pixels.tobytes(), dtype=np.uint8).reshape(
            spec.height, packed_row_bytes
        )
        return self.message(
            "sensor_msgs/msg/Image",
            header=self.header(
                timestamp_ns,
                index,
                "synthetic_depth_optical_frame" if depth else "synthetic_color_optical_frame",
            ),
            height=spec.height,
            width=spec.width,
            encoding=encoding,
            is_bigendian=int(depth and spec.depth_bigendian),
            step=step,
            data=rows.reshape(-1),
        )

    def imu(self, index: int, timestamp_ns: int) -> Any:
        return self.message(
            "sensor_msgs/msg/Imu",
            header=self.header(timestamp_ns, index, "synthetic_imu_frame"),
            orientation=self.quaternion((0.0, 0.0, 0.0, 1.0)),
            orientation_covariance=np.array([-1.0] + [0.0] * 8, dtype=np.float64),
            angular_velocity=self.vector((0.125 + index, -0.25 - index, 0.5 * index)),
            angular_velocity_covariance=np.zeros(9, dtype=np.float64),
            linear_acceleration=self.vector((0.25 + index, -0.5 - index, 9.75 + 0.125 * index)),
            linear_acceleration_covariance=np.zeros(9, dtype=np.float64),
        )

    def static_messages(self) -> list[tuple[str, Any]]:
        """Return calibration and synthetic device information in fixed order."""
        spec = self.spec
        result: list[tuple[str, Any]] = []
        for depth, sensor, stream in ((False, 1, "Color"), (True, 0, "Depth")):
            result.append(
                (
                    f"/device_0/sensor_{sensor}/{stream}_0/info/camera_info",
                    self.camera_info(depth=depth),
                )
            )
        for sensor, stream, translation, rotation in (
            (0, "Depth", (0.002, -0.003, 0.004), (0.0, 0.0, 0.0, 1.0)),
            (1, "Color", (0.025, -0.005, 0.002), (0.0, 0.0, 0.6, 0.8)),
        ):
            transform = self.message(
                "geometry_msgs/msg/Transform",
                translation=self.vector(translation),
                rotation=self.quaternion(rotation),
            )
            result.append((f"/device_0/sensor_{sensor}/{stream}_0/tf/0", transform))
        fps = max(1, round(1_000_000_000 / spec.frame_period_ns))
        for sensor, stream, encoding in (
            (1, "Color", "rgb8"),
            (0, "Depth", "16UC1"),
            (2, "Accel", "motion_xyz32f"),
            (2, "Gyro", "motion_xyz32f"),
        ):
            result.append(
                (
                    f"/device_0/sensor_{sensor}/{stream}_0/info",
                    self.message(
                        _STREAM_INFO_TYPE, fps=fps, encoding=encoding, is_recommended=True
                    ),
                )
            )
        for key, value in (
            ("Name", "Synthetic RealSense D435i"),
            ("Serial Number", "SYNTHETIC-0001"),
            ("Firmware Version", "0.0.synthetic"),
        ):
            result.append(
                (
                    "/device_0/info",
                    self.message("diagnostic_msgs/msg/KeyValue", key=key, value=value),
                )
            )
        for sensor, name in ((0, "Stereo Module"), (1, "RGB Camera"), (2, "Motion Module")):
            result.append(
                (
                    f"/device_0/sensor_{sensor}/info",
                    self.message("diagnostic_msgs/msg/KeyValue", key="Name", value=name),
                )
            )
        for option, option_value, description in (
            ("Depth Units", spec.depth_scale, "Synthetic depth unit in metres"),
            ("Exposure", 156.0, "Synthetic exposure in microseconds"),
        ):
            prefix = f"/device_0/sensor_0/option/{option}"
            result.extend(
                (
                    (f"{prefix}/value", self.message("std_msgs/msg/Float64", data=option_value)),
                    (
                        f"{prefix}/description",
                        self.message("std_msgs/msg/String", data=description),
                    ),
                )
            )
        return result


def write_synthetic_rosbag(output_path: Path | str, spec: SyntheticBagSpec | None = None) -> Path:
    """Write a real ROS1 bag and return its path, refusing to overwrite files.

    Memory usage is proportional to one RGB-D frame, independent of the
    requested recording length.  Custom StreamInfo definitions are embedded
    so ``rosbags.highlevel.AnyReader`` can deserialize the file independently.
    """
    path = Path(output_path)
    spec = spec if spec is not None else SyntheticBagSpec()
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    factory = _MessageFactory(spec)
    connections: dict[str, Any] = {}
    with Writer(path) as writer:

        def write(topic: str, timestamp: int, message: Any) -> None:
            msgtype = message.__msgtype__
            if topic not in connections:
                connections[topic] = writer.add_connection(
                    topic, msgtype, typestore=factory.typestore, callerid="synthetic_rosbag"
                )
            data = factory.typestore.serialize_ros1(message, msgtype)
            writer.write(connections[topic], timestamp, data)

        for topic, message in factory.static_messages():
            write(topic, spec.start_time_ns - 1_000_000, message)
        for index in range(spec.frame_count):
            timestamp = spec.start_time_ns + index * spec.frame_period_ns
            write(COLOR_TOPIC, timestamp, factory.image(index, timestamp, depth=False))
            write(DEPTH_TOPIC, timestamp, factory.image(index, timestamp, depth=True))
            write(ACCEL_TOPIC, timestamp + 1_000_000, factory.imu(index, timestamp + 1_000_000))
            write(GYRO_TOPIC, timestamp + 2_000_000, factory.imu(index, timestamp + 2_000_000))
    return path


def main() -> int:
    """Create an artificial bag using only the requested local output path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_bag", type=Path)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--frames", type=int, default=4)
    parser.add_argument("--frame-period-ns", type=int, default=40_000_000)
    parser.add_argument("--depth-scale", type=float, default=0.002)
    parser.add_argument("--row-padding-bytes", type=int, default=0)
    parser.add_argument("--depth-bigendian", action="store_true")
    args = parser.parse_args()
    try:
        spec = SyntheticBagSpec(
            width=args.width,
            height=args.height,
            frame_count=args.frames,
            frame_period_ns=args.frame_period_ns,
            depth_scale=args.depth_scale,
            row_padding_bytes=args.row_padding_bytes,
            depth_bigendian=args.depth_bigendian,
        )
        path = write_synthetic_rosbag(args.output_bag, spec)
    except (ValueError, OSError, WriterError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(f"Generated synthetic ROS1 bag: {path}")
    print(f"RGB-D {spec.width}x{spec.height}, {spec.frame_count} frames, with IMU and calibration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
