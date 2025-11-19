# PyVRS API Investigation

**Module:** `pyvrs`

**Date:** 2025-11-19

---

## Top-Level Attributes

**Total public attributes:** 35

## Classes (25)

### `AsyncMultiReader`

**Methods:** 36

- `__init__` (signature unavailable)
- `async_read_record` (signature unavailable)
- `close` (signature unavailable)
- `enable_all_streams` (signature unavailable)
- `enable_stream` (signature unavailable)
- `enable_streams` (signature unavailable)
- `enable_streams_by_indexes` (signature unavailable)
- `find_stream` (signature unavailable)
- `get_all_records_info` (signature unavailable)
- `get_available_record_types` (signature unavailable)
- `get_available_records_size` (signature unavailable)
- `get_available_stream_ids` (signature unavailable)
- `get_enabled_streams` (signature unavailable)
- `get_enabled_streams_records_info` (signature unavailable)
- `get_encoding` (signature unavailable)
- `get_file_chunks` (signature unavailable)
- `get_max_available_timestamp` (signature unavailable)
- `get_min_available_timestamp` (signature unavailable)
- `get_nearest_record_index_by_time` (signature unavailable)
- `get_next_index` (signature unavailable)
- `get_prev_index` (signature unavailable)
- `get_record_index_by_time` (signature unavailable)
- `get_records_count` (signature unavailable)
- `get_records_info` (signature unavailable)
- `get_stream_id_for_index` (signature unavailable)
- `get_stream_info` (signature unavailable)
- `get_streams` (signature unavailable)
- `get_tags` (signature unavailable)
- `get_timestamp_for_index` (signature unavailable)
- `get_timestamp_list_for_indices` (signature unavailable)
- `open` (signature unavailable)
- `record_count_by_type_from_stream_id` (signature unavailable)
- `regenerate_enabled_indices` (signature unavailable)
- `set_encoding` (signature unavailable)
- `set_image_conversion` (signature unavailable)
- `skip_trailing_blocks` (signature unavailable)


### `AsyncReader`

**Methods:** 39

- `__init__` (signature unavailable)
- `async_read_record` (signature unavailable)
- `close` (signature unavailable)
- `enable_all_streams` (signature unavailable)
- `enable_stream` (signature unavailable)
- `enable_streams` (signature unavailable)
- `enable_streams_by_indexes` (signature unavailable)
- `find_stream` (signature unavailable)
- `get_all_records_info` (signature unavailable)
- `get_available_record_types` (signature unavailable)
- `get_available_records_size` (signature unavailable)
- `get_available_stream_ids` (signature unavailable)
- `get_enabled_streams` (signature unavailable)
- `get_enabled_streams_records_info` (signature unavailable)
- `get_encoding` (signature unavailable)
- `get_file_chunks` (signature unavailable)
- `get_max_available_timestamp` (signature unavailable)
- `get_min_available_timestamp` (signature unavailable)
- `get_nearest_record_index_by_time` (signature unavailable)
- `get_next_index` (signature unavailable)
- `get_prev_index` (signature unavailable)
- `get_record_index_by_time` (signature unavailable)
- `get_records_count` (signature unavailable)
- `get_records_info` (signature unavailable)
- `get_stream_for_flavor` (signature unavailable)
- `get_stream_id_for_index` (signature unavailable)
- `get_stream_info` (signature unavailable)
- `get_streams` (signature unavailable)
- `get_tags` (signature unavailable)
- `get_timestamp_for_index` (signature unavailable)
- `get_timestamp_list_for_indices` (signature unavailable)
- `might_contain_audio` (signature unavailable)
- `might_contain_images` (signature unavailable)
- `open` (signature unavailable)
- `record_count_by_type_from_stream_id` (signature unavailable)
- `regenerate_enabled_indices` (signature unavailable)
- `set_encoding` (signature unavailable)
- `set_image_conversion` (signature unavailable)
- `skip_trailing_blocks` (signature unavailable)


### `AsyncVRSReader`

**Methods:** 31

- `__init__(self, path: Union[pathlib.Path, str, List[pathlib.Path], List[str], Dict[str, Union[int, str, List[str]]], vrsbindings.FileSpec, List[vrsbindings.FileSpec]], auto_read_configuration_records: bool = True, encoding: str = 'utf-8-safe', multi_path: bool = False) -> None`
- `close(self)`
- `filtered_by_fields(self, stream_ids: Union[Set[str], str, NoneType] = None, record_types: Union[Set[str], str, NoneType] = None, min_timestamp: Optional[float] = None, max_timestamp: Optional[float] = None) -> pyvrs.filter.AsyncFilteredVRSReader`
- `find_stream(self, recordable_type_id: int, tag_name: str, tag_value: str) -> str`
- `find_streams(self, recordable_type_id: int, flavor: str = '') -> List[str]`
- `get_estimated_frame_rate(self, stream_id: str) -> float`
- `get_record_index_by_time(self, stream_id: str, timestamp: float, epsilon: Optional[float] = None, record_type: Optional[vrsbindings.RecordType] = None) -> int`
- `get_records_count(self, stream_id: str, record_type: vrsbindings.RecordType) -> int`
- `get_serial_number_for_stream(self, stream_id: str) -> str`
- `get_stream_for_flavor(self, recordable_type_id: int, flavor: str, index_number: int = 0) -> str`
- `get_stream_for_serial_number(self, serial_number: str) -> str`
- `get_stream_info(self, stream_id: str) -> Dict[str, str]`
- `get_timestamp_for_index(self, index: int) -> float`
- `get_timestamp_list(self, indices: Optional[List[int]] = None) -> List[float]`
- `might_contain_audio(self, stream_id: str) -> bool`
- `might_contain_images(self, stream_id: str) -> bool`
- `read_next_record(self, stream_id: str, record_type: str, index: int) -> Optional[pyvrs.record.VRSRecord]`
- `read_prev_record(self, stream_id: str, record_type: str, index: int) -> Optional[pyvrs.record.VRSRecord]`
- `read_record_by_time(self, stream_id: str, timestamp: float, epsilon: Optional[float] = None, record_type: Optional[vrsbindings.RecordType] = None) -> pyvrs.record.VRSRecord`
- `set_image_conversion(self, conversion: vrsbindings.ImageConversion) -> None`
- `set_stream_image_conversion(self, stream_id: str, conversion: vrsbindings.ImageConversion) -> None`
- `set_stream_type_image_conversion(self, recordable_type_id: str, conversion: vrsbindings.ImageConversion) -> int`
- `skip_trailing_blocks(self, recordable_type_id: int, record_type: vrsbindings.RecordType, first_trailing_content_block_index: int) -> None`


### `AudioSpec`

**Methods:** 9

- `__init__(self, /, *args, **kwargs)`
- `items` (signature unavailable)


### `AwaitableRecord`

**Methods:** 1

- `__init__(self, /, *args, **kwargs)`


### `BinaryBuffer`

**Methods:** 1

- `__init__(self, /, *args, **kwargs)`


### `Buffer`

**Methods:** 4

- `__init__(self, /, *args, **kwargs)`
- `decompress` (signature unavailable)
- `jpg_compress` (signature unavailable)
- `jxl_compress` (signature unavailable)


### `CompressionPreset`

**Description:** Members:

**Methods:** 12

- `__init__` (signature unavailable)


### `ContentBlock`

**Methods:** 3

- `__init__(self, /, *args, **kwargs)`
- `items` (signature unavailable)


### `FileSpec`

**Methods:** 7

- `__init__` (signature unavailable)
- `get_chunk_sizes` (signature unavailable)
- `get_chunks` (signature unavailable)
- `get_easy_path` (signature unavailable)
- `get_filehandler_name` (signature unavailable)
- `get_filename` (signature unavailable)
- `get_uri` (signature unavailable)


### `ImageBuffer`

**Methods:** 7

- `__init__` (signature unavailable)
- `decompress` (signature unavailable)
- `jpg_compress` (signature unavailable)
- `jxl_compress` (signature unavailable)


### `ImageConversion`

**Description:** Members:

**Methods:** 9

- `__init__` (signature unavailable)


### `ImageFormat`

**Description:** Members:

**Methods:** 9

- `__init__` (signature unavailable)


### `ImageSpec`

**Methods:** 18

- `__init__(self, /, *args, **kwargs)`
- `get_height` (signature unavailable)
- `get_image_format` (signature unavailable)
- `get_pixel_format` (signature unavailable)
- `get_stride` (signature unavailable)
- `get_width` (signature unavailable)
- `items` (signature unavailable)


### `MultiReader`

**Methods:** 39

- `__init__` (signature unavailable)
- `close` (signature unavailable)
- `enable_all_streams` (signature unavailable)
- `enable_stream` (signature unavailable)
- `enable_streams` (signature unavailable)
- `enable_streams_by_indexes` (signature unavailable)
- `find_stream` (signature unavailable)
- `get_all_records_info` (signature unavailable)
- `get_available_record_types` (signature unavailable)
- `get_available_records_size` (signature unavailable)
- `get_available_stream_ids` (signature unavailable)
- `get_enabled_streams` (signature unavailable)
- `get_enabled_streams_records_info` (signature unavailable)
- `get_encoding` (signature unavailable)
- `get_file_chunks` (signature unavailable)
- `get_max_available_timestamp` (signature unavailable)
- `get_min_available_timestamp` (signature unavailable)
- `get_nearest_record_index_by_time` (signature unavailable)
- `get_next_index` (signature unavailable)
- `get_prev_index` (signature unavailable)
- `get_record_index_by_time` (signature unavailable)
- `get_records_count` (signature unavailable)
- `get_records_info` (signature unavailable)
- `get_stream_id_for_index` (signature unavailable)
- `get_stream_info` (signature unavailable)
- `get_streams` (signature unavailable)
- `get_tags` (signature unavailable)
- `get_timestamp_for_index` (signature unavailable)
- `get_timestamp_list_for_indices` (signature unavailable)
- `goto_record` (signature unavailable)
- `goto_time` (signature unavailable)
- `open` (signature unavailable)
- `read_next_record` (signature unavailable)
- `read_record` (signature unavailable)
- `record_count_by_type_from_stream_id` (signature unavailable)
- `regenerate_enabled_indices` (signature unavailable)
- `set_encoding` (signature unavailable)
- `set_image_conversion` (signature unavailable)
- `skip_trailing_blocks` (signature unavailable)


### `PixelFormat`

**Description:** Members:

**Methods:** 26

- `__init__` (signature unavailable)


### `Reader`

**Methods:** 43

- `__init__` (signature unavailable)
- `close` (signature unavailable)
- `enable_all_streams` (signature unavailable)
- `enable_stream` (signature unavailable)
- `enable_streams` (signature unavailable)
- `enable_streams_by_indexes` (signature unavailable)
- `find_stream` (signature unavailable)
- `get_all_records_info` (signature unavailable)
- `get_available_record_types` (signature unavailable)
- `get_available_records_size` (signature unavailable)
- `get_available_stream_ids` (signature unavailable)
- `get_enabled_streams` (signature unavailable)
- `get_enabled_streams_records_info` (signature unavailable)
- `get_encoding` (signature unavailable)
- `get_estimated_frame_rate` (signature unavailable)
- `get_file_chunks` (signature unavailable)
- `get_max_available_timestamp` (signature unavailable)
- `get_min_available_timestamp` (signature unavailable)
- `get_nearest_record_index_by_time` (signature unavailable)
- `get_next_index` (signature unavailable)
- `get_prev_index` (signature unavailable)
- `get_record_index_by_time` (signature unavailable)
- `get_records_count` (signature unavailable)
- `get_records_info` (signature unavailable)
- `get_stream_for_flavor` (signature unavailable)
- `get_stream_id_for_index` (signature unavailable)
- `get_stream_info` (signature unavailable)
- `get_streams` (signature unavailable)
- `get_tags` (signature unavailable)
- `get_timestamp_for_index` (signature unavailable)
- `get_timestamp_list_for_indices` (signature unavailable)
- `goto_record` (signature unavailable)
- `goto_time` (signature unavailable)
- `might_contain_audio` (signature unavailable)
- `might_contain_images` (signature unavailable)
- `open` (signature unavailable)
- `read_next_record` (signature unavailable)
- `read_record` (signature unavailable)
- `record_count_by_type_from_stream_id` (signature unavailable)
- `regenerate_enabled_indices` (signature unavailable)
- `set_encoding` (signature unavailable)
- `set_image_conversion` (signature unavailable)
- `skip_trailing_blocks` (signature unavailable)


### `Record`

**Methods:** 1

- `__init__(self, /, *args, **kwargs)`


### `RecordType`

**Description:** Members:

**Methods:** 7

- `__init__` (signature unavailable)


### `RecordableId`

**Methods:** 7

- `__init__(self, /, *args, **kwargs)`
- `get_instance_id` (signature unavailable)
- `get_name` (signature unavailable)
- `get_numeric_name` (signature unavailable)
- `get_type_id` (signature unavailable)
- `get_type_name` (signature unavailable)
- `is_valid` (signature unavailable)


### `RecordableTypeId`

**Description:** Members:

**Methods:** 3

- `__init__` (signature unavailable)


### `StreamNotFoundError`

**Methods:** 3

- `__init__(self, /, *args, **kwargs)`
- `with_traceback` (signature unavailable)


### `SyncVRSReader`

**Methods:** 31

- `__init__(self, path: Union[pathlib.Path, str, List[pathlib.Path], List[str], Dict[str, Union[int, str, List[str]]], vrsbindings.FileSpec, List[vrsbindings.FileSpec]], auto_read_configuration_records: bool = True, encoding: str = 'utf-8-safe', multi_path: bool = False) -> None`
- `close(self)`
- `filtered_by_fields(self, *, stream_ids: Union[Set[str], str, NoneType] = None, record_types: Union[Set[str], str, NoneType] = None, min_timestamp: Optional[float] = None, max_timestamp: Optional[float] = None) -> pyvrs.filter.SyncFilteredVRSReader`
- `find_stream(self, recordable_type_id: int, tag_name: str, tag_value: str) -> str`
- `find_streams(self, recordable_type_id: int, flavor: str = '') -> List[str]`
- `get_estimated_frame_rate(self, stream_id: str) -> float`
- `get_record_index_by_time(self, stream_id: str, timestamp: float, epsilon: Optional[float] = None, record_type: Optional[vrsbindings.RecordType] = None) -> int`
- `get_records_count(self, stream_id: str, record_type: vrsbindings.RecordType) -> int`
- `get_serial_number_for_stream(self, stream_id: str) -> str`
- `get_stream_for_flavor(self, recordable_type_id: int, flavor: str, index_number: int = 0) -> str`
- `get_stream_for_serial_number(self, serial_number: str) -> str`
- `get_stream_info(self, stream_id: str) -> Dict[str, str]`
- `get_timestamp_for_index(self, index: int) -> float`
- `get_timestamp_list(self, indices: Optional[List[int]] = None) -> List[float]`
- `might_contain_audio(self, stream_id: str) -> bool`
- `might_contain_images(self, stream_id: str) -> bool`
- `read_next_record(self, stream_id: str, record_type: str, index: int) -> Optional[pyvrs.record.VRSRecord]`
- `read_prev_record(self, stream_id: str, record_type: str, index: int) -> Optional[pyvrs.record.VRSRecord]`
- `read_record_by_time(self, stream_id: str, timestamp: float, epsilon: Optional[float] = None, record_type: Optional[vrsbindings.RecordType] = None) -> pyvrs.record.VRSRecord`
- `set_image_conversion(self, conversion: vrsbindings.ImageConversion) -> None`
- `set_stream_image_conversion(self, stream_id: str, conversion: vrsbindings.ImageConversion) -> None`
- `set_stream_type_image_conversion(self, recordable_type_id: str, conversion: vrsbindings.ImageConversion) -> int`
- `skip_trailing_blocks(self, recordable_type_id: int, record_type: vrsbindings.RecordType, first_trailing_content_block_index: int) -> None`


### `TimestampNotFoundError`

**Methods:** 3

- `__init__(self, /, *args, **kwargs)`
- `with_traceback` (signature unavailable)


### `VRSRecord`

**Methods:** 20

- `__init__(self, /, *args, **kwargs)`
- `items` (signature unavailable)


## Functions (0)


## Submodules (6)

### `base`

**Public attributes:** 15
- ABC, Any, BaseVRSReader, Dict, ImageConversion, Iterator, List, Mapping, Optional, RecordType, Set, Union, VRSReaderSlice, VRSRecord, abstractmethod

### `filter`

**Public attributes:** 22
- ABC, Any, AsyncFilteredVRSReader, BaseVRSReader, FilteredVRSReader, ImageConversion, List, Mapping, Optional, RecordFilter, RecordType, Set, SyncFilteredVRSReader, Union, VRSReaderSlice, VRSRecord, abstractmethod, bisect, dataclass, get_recordable_type_id_name
  ... and 2 more

### `reader`

**Public attributes:** 39
- ABC, Any, AsyncFilteredVRSReader, AsyncIterable, AsyncMultiReader, AsyncReader, AsyncVRSReader, AsyncVRSReaderSlice, BaseVRSReader, Dict, FileSpec, FilteredVRSReader, ImageConversion, List, Mapping, MultiReader, Optional, Path, PathType, Reader
  ... and 19 more

### `record`

**Public attributes:** 10
- Callable, Sequence, T, TypeVar, Union, VRSBlocks, VRSRecord, np, partial, stringify_metadata_keys

### `slice`

**Public attributes:** 10
- AsyncVRSReaderSlice, List, Path, Sequence, TYPE_CHECKING, Union, VRSReaderSlice, VRSRecord, async_index_or_slice_records, index_or_slice_records

### `utils`

**Public attributes:** 17
- Any, Callable, Dict, Iterable, Mapping, Set, T, Tuple, TypeVar, filter_by_record_type, filter_by_stream_ids, fnmatch, get_recordable_type_id_name, recordable_type_id_name, string_of_set, stringify_metadata_keys, tags_to_justified_table_str

## Constants/Other (4)

- `extract_audio_track`: `builtin_function_or_method`
- `recordable_type_id_name`: `builtin_function_or_method`
- `records_checksum`: `builtin_function_or_method`
- `verbatim_checksum`: `builtin_function_or_method`

---

## Key Findings

### Reader Classes

- `AsyncMultiReader`: Used for reading VRS files
- `AsyncReader`: Used for reading VRS files
- `AsyncVRSReader`: Used for reading VRS files
- `MultiReader`: Used for reading VRS files
- `Reader`: Used for reading VRS files
- `SyncVRSReader`: Used for reading VRS files

### Record Classes

- `AwaitableRecord`: Represents VRS records
- `Record`: Represents VRS records
- `RecordType`: Represents VRS records
- `RecordableId`: Represents VRS records
- `RecordableTypeId`: Represents VRS records
- `VRSRecord`: Represents VRS records

### Spec Classes

- `AudioSpec`: Configuration specifications
- `FileSpec`: Configuration specifications
- `ImageSpec`: Configuration specifications

### Note

- **Module name:** The package is named `vrs` but must be imported as `pyvrs`
- **Writer support:** No explicit Writer class found in top-level API
  - VRS writing may be done through C++ bindings or different interface
  - Further investigation of submodules may be needed

---

## Critical Finding: PyVRS is Read-Only

**Investigation Date:** 2025-11-19

### Summary

PyVRS (Python bindings for VRS) **does NOT support writing VRS files**. The library only provides reading functionality.

### Evidence

1. **PyVRS Python API**: No Writer class found in `pyvrs` module or `vrsbindings`
2. **PyVRS Documentation**: Only contains reader, record, filter, slice, and utils modules
3. **PyVRS GitHub**: No mention of file creation or writing capabilities

### VRS C++ Library Status

The underlying **VRS C++ library DOES support writing**:
- `RecordFileWriter` class exists in C++ API
- Sample code `SampleRecordAndPlay.cpp` demonstrates file creation
- `vrs` command-line tool can create VRS files
- Supports multi-threaded recording with lz4/zstd compression

### Problem

The Python bindings (`pyvrs`) do not expose the writing functionality from the C++ library.

### Possible Solutions

#### Option 1: Use C++ VRS Library Directly
- Write C++ program using `RecordFileWriter`
- Call from Python using subprocess or ctypes
- Requires building VRS C++ library from source

#### Option 2: Create Custom Python Bindings
- Use pybind11 to create Python bindings for `RecordFileWriter`
- Requires C++ development and VRS library source
- Time-consuming but provides clean Python API

#### Option 3: Use VRS Command-Line Tool
- Build VRS C++ library to get `vrs` CLI tool
- Create VRS files using CLI from Python subprocess
- Requires VRS build dependencies (boost, fmt, lz4, zstd)

#### Option 4: Alternative Approach
- Consider different file format (HDF5, Apache Parquet, etc.)
- Abandon VRS conversion goal
- Not aligned with project objectives

### Recommendation

**Proceed with Option 1 or 3**: Build VRS C++ library and either:
- Use CLI tool via subprocess (faster to implement)
- Write C++ wrapper program (more control)

This represents a significant deviation from the original work plan, which assumed PyVRS would have writing capabilities.
