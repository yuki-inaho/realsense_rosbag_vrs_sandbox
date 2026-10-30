"""Versioned stream tags shared by the official VRS writer and repository reader.

Version 2 preserves real image shapes and pixel formats, stores IMU components
as typed metadata, and uses an explicit base64 field for otherwise opaque bytes.
Files without this version tag retain their historical reader interpretation.
The official sample factories still use the UnitTest1 recordable type; these
tags do not claim compatibility with a device-specific schema such as Aria.
"""

SCHEMA_VERSION_TAG = "vrs_sandbox_schema_version"
SCHEMA_VERSION = "2"
PAYLOAD_ENCODING_TAG = "payload_encoding"

USER_STREAM_ID_TAG = "user_stream_id"
USER_STREAM_NAME_TAG = "user_stream_name"
CONFIG_JSON_TAG = "config_json"

NATIVE_IMAGE = "native_image"
IMU_VECTOR = "imu_xyz_f64le"
OPAQUE_BYTES = "opaque_base64"

IMU_VECTOR_FIELD = "doubles"
OPAQUE_BYTES_FIELD = "some_string"
