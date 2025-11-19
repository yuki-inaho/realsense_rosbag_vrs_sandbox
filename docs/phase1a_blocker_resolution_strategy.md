# Phase 1A Blocker Resolution Strategy
**Created**: 2025-11-19
**Purpose**: Complete implementation of pyvrs_writer C++ VRS record writing functionality

## 1. Problem Statement

### Current State
The `pyvrs_writer/src/vrs_writer.cpp` implementation contains stub methods that prevent actual VRS record writing:

**Location 1: Lines 65-84** - Empty writeConfiguration() and writeData() methods:
```cpp
void VRSWriter::writeConfiguration(uint32_t streamId, const std::string& jsonConfig) {
  // TODO: 実際のVRS APIに合わせて実装
  // 現在はスタブ実装（テストを通すため）
}

void VRSWriter::writeData(uint32_t streamId, double timestamp,
                          const std::vector<uint8_t>& data) {
  // TODO: 実際のVRS APIに合わせて実装
  // 現在はスタブ実装（テストを通すため）
}
```

**Location 2: Lines 21-28** - SimpleRecordable returns nullptr:
```cpp
const vrs::Record* createConfigurationRecord() override {
  return nullptr;  // TODO: 実際のConfiguration recordを返す
}

const vrs::Record* createStateRecord() override {
  return nullptr;  // TODO: 実際のState recordを返す
}
```

### Impact
- VRS files created by pyvrs_writer contain 0 records
- PyVRS cannot read these files (no streams/data found)
- Phase 3 VRS Reader tests failing: 4/8 tests (get_stream_ids, read_configuration, read_data_records, get_record_count)
- Blocks entire ROSbag→VRS conversion pipeline

### Success Criteria
1. VRS files created by pyvrs_writer contain actual configuration and data records
2. PyVRS can successfully read these files
3. Phase 2 tests (10/10) still pass
4. Phase 3 tests (8/8) all pass
5. Records contain correct JSON configuration and binary data
6. Timestamps are properly stored

---

## 2. VRS C++ API Research Plan

### Key VRS Components to Investigate

#### 2.1 RecordFileWriter API
- `addRecordable(Recordable*)` - Already used ✓
- `writeToFile(const string& path)` - Already used ✓
- **Need to research**:
  - How to trigger actual record creation during writeToFile()
  - Whether we need to call createRecord() explicitly
  - Timing of configuration vs data records

#### 2.2 Recordable API
- `createConfigurationRecord()` - Currently returns nullptr ✗
- `createStateRecord()` - Currently returns nullptr ✗
- **Need to research**:
  - Proper return type and ownership (unique_ptr? raw pointer?)
  - When VRS calls these methods
  - How to create Record objects

#### 2.3 Record and DataLayout
- **Need to research**:
  - `vrs::Record` class construction
  - `vrs::DataLayout` for structured data
  - `vrs::DataPiece` for raw bytes
  - How to set record type (CONFIGURATION vs DATA)
  - How to set timestamps for DATA records

#### 2.4 StreamId
- Currently using uint32_t directly
- **Need to research**:
  - `vrs::StreamId` class usage
  - Proper RecordableTypeId values (currently using UnitTest1)
  - Stream naming conventions

### Research Sources
1. VRS official documentation: https://github.com/facebookresearch/vrs
2. VRS header files in `/usr/local/include/vrs/`
3. VRS example code (if available)
4. Existing VRS C++ projects on GitHub

---

## 3. Implementation Design

### 3.1 Architecture Overview

```
Python (vrs_writer.py)
    ↓ calls
pybind11 bindings (bindings.cpp)
    ↓ calls
VRSWriter C++ class (vrs_writer.cpp)
    ↓ uses
SimpleRecordable + VRS C++ library
    ↓ creates
VRS file with records
```

### 3.2 Data Flow

#### Configuration Record Flow
1. Python: `writer.write_configuration(1001, {"width": 640})`
2. C++ VRSWriter::writeConfiguration() receives streamId=1001, jsonConfig='{"width":640}'
3. **Need to implement**: Store jsonConfig in recordable for later retrieval
4. VRS calls SimpleRecordable::createConfigurationRecord()
5. **Need to implement**: Return Record containing JSON data
6. VRS writes record to file during writeToFile()

#### Data Record Flow
1. Python: `writer.write_data(1001, 0.033, b"image_bytes")`
2. C++ VRSWriter::writeData() receives streamId=1001, timestamp=0.033, data=[...]
3. **Need to implement**: Queue data record in recordable
4. **Need to implement**: VRS record creation with timestamp and data
5. VRS writes record to file during writeToFile()

### 3.3 Storage Strategy

**Option A: Store in Recordable** (Recommended)
```cpp
class SimpleRecordable : public vrs::Recordable {
private:
  std::string configJson_;  // Store configuration
  struct DataRecord {
    double timestamp;
    std::vector<uint8_t> data;
  };
  std::vector<DataRecord> dataRecords_;  // Queue data records
};
```

**Option B: Store in VRSWriter::Impl**
- Keep Recordable minimal
- Store data in pImpl_->recordables map

**Decision**: Use Option A - Recordable owns its data (cleaner separation)

### 3.4 VRS API Usage Pattern (Hypothesis)

Based on VRS architecture, likely pattern:
```cpp
// In writeConfiguration():
void VRSWriter::writeConfiguration(uint32_t streamId, const std::string& jsonConfig) {
  auto& recordable = pImpl_->recordables[streamId];
  recordable->setConfigurationJson(jsonConfig);
  // VRS will call createConfigurationRecord() during writeToFile()
}

// In SimpleRecordable:
const vrs::Record* createConfigurationRecord() override {
  // Create Record with configJson_ data
  // Use DataLayout or DataPiece
  return recordPtr;  // Or return by unique_ptr?
}
```

---

## 4. Implementation Plan

### Phase A: Research (Est. 15-20 min)
1. **Examine VRS headers** in `/usr/local/include/vrs/`:
   - `RecordFileWriter.h`
   - `Recordable.h`
   - `Record.h`
   - `DataLayout.h`
   - `StreamId.h`

2. **Search for VRS examples**:
   - Look for VRS test files in installed VRS directory
   - Search GitHub for VRS usage examples
   - Check VRS documentation

3. **Document findings**:
   - Record creation API
   - Data layout API
   - Ownership and lifetime management
   - Configuration vs Data record differences

### Phase B: Design Refinement (Est. 5-10 min)
1. Update SimpleRecordable class design based on research
2. Design writeConfiguration() implementation
3. Design writeData() implementation
4. Plan memory management strategy
5. Identify potential error cases

### Phase C: Implementation (Est. 20-30 min)
1. **Update SimpleRecordable class**:
   ```cpp
   class SimpleRecordable : public vrs::Recordable {
   private:
     uint32_t streamId_;
     std::string configJson_;
     std::vector<DataRecord> dataRecords_;
   public:
     void setConfiguration(const std::string& json);
     void addDataRecord(double timestamp, const std::vector<uint8_t>& data);
     const vrs::Record* createConfigurationRecord() override;
     const vrs::Record* createStateRecord() override;
   };
   ```

2. **Implement VRSWriter::writeConfiguration()**:
   - Validate streamId exists
   - Store JSON in corresponding recordable
   - Handle errors

3. **Implement VRSWriter::writeData()**:
   - Validate streamId exists
   - Queue data record with timestamp
   - Handle errors

4. **Implement createConfigurationRecord()**:
   - Create VRS Record with JSON data
   - Set proper record type
   - Return record (check ownership)

5. **Implement createStateRecord()**:
   - Return nullptr if not needed, or
   - Create minimal state record if required

### Phase D: Build and Test (Est. 10-15 min)
1. Rebuild pyvrs_writer:
   ```bash
   cd pyvrs_writer
   python setup.py build_ext --inplace
   cp build/lib.linux-*/pyvrs_writer/_pyvrs_writer.*.so python/pyvrs_writer/
   ```

2. Run Phase 2 tests (should still pass):
   ```bash
   PYTHONPATH=pyvrs_writer/python pytest tests/test_vrs_writer.py -v
   ```

3. Run Phase 3 tests (should now pass all 8):
   ```bash
   PYTHONPATH=pyvrs_writer/python pytest tests/test_vrs_reader.py -v
   ```

4. Debug any failures

### Phase E: Validation (Est. 5-10 min)
1. Verify VRS file contents with PyVRS:
   ```python
   reader = pyvrs.SyncVRSReader("test.vrs")
   for record in reader:
       print(record.stream_id, record.record_type, record.timestamp)
   ```

2. Check record counts match expectations
3. Verify configuration JSON is readable
4. Verify data payloads are correct
5. Verify timestamps are preserved

---

## 5. Risk Assessment

### High Risk
- **VRS API complexity**: VRS API may be more complex than anticipated
  - Mitigation: Thorough header examination and example code research
- **Memory management**: Incorrect pointer ownership could cause crashes
  - Mitigation: Carefully read VRS documentation on Record ownership

### Medium Risk
- **Data layout requirements**: VRS may require specific DataLayout structure
  - Mitigation: Start with simple raw bytes, refine if needed
- **Recordable lifecycle**: Unclear when VRS calls createConfigurationRecord()
  - Mitigation: Add debug logging to understand call sequence

### Low Risk
- **Build issues**: C++ compilation errors
  - Mitigation: Incremental compilation and testing
- **Test compatibility**: Phase 2 tests may break
  - Mitigation: These tests don't read VRS files, should be unaffected

---

## 6. Success Metrics

### Functional Requirements
- [ ] VRS files contain configuration records (1 per stream)
- [ ] VRS files contain data records (N per stream)
- [ ] PyVRS can enumerate stream IDs
- [ ] PyVRS can read configuration JSON
- [ ] PyVRS can read data records with timestamps
- [ ] Timestamps match input values (within epsilon)
- [ ] Data payloads match input bytes

### Test Requirements
- [ ] Phase 2: test_vrs_writer.py - 10/10 PASSING
- [ ] Phase 3: test_vrs_reader.py - 8/8 PASSING
- [ ] No segfaults or memory leaks
- [ ] No compiler warnings

### Code Quality
- [ ] No TODO comments remaining
- [ ] Proper error handling
- [ ] RAII/smart pointer usage
- [ ] Clear variable names
- [ ] Comments explaining VRS API usage

---

## 7. Rollback Plan

If implementation fails or introduces regressions:

1. **Preserve current state**:
   ```bash
   git stash  # Save work in progress
   git checkout pyvrs_writer/src/vrs_writer.cpp  # Restore stub version
   ```

2. **Identify blocker**:
   - Document specific VRS API issue
   - Gather error messages and stack traces
   - Research specific problem

3. **Alternative approaches**:
   - Try simpler VRS API if available
   - Use different Record creation method
   - Consult VRS community/issues

4. **Escalation**:
   - Review VRS source code directly
   - Create minimal reproduction case
   - File VRS GitHub issue if bug found

---

## 8. Timeline Estimate

| Phase | Activity | Est. Time |
|-------|----------|-----------|
| A | Research VRS API | 15-20 min |
| B | Design refinement | 5-10 min |
| C | Implementation | 20-30 min |
| D | Build and test | 10-15 min |
| E | Validation | 5-10 min |
| **Total** | | **55-85 min** |

---

## 9. Next Steps

1. ✅ Create this strategy document
2. ⏭️ Begin Phase A: Research VRS API headers
3. ⏭️ Document VRS API findings
4. ⏭️ Proceed with implementation phases B-E
5. ⏭️ Update work plan checklist when complete

---

## References

- VRS GitHub: https://github.com/facebookresearch/vrs
- VRS Documentation: https://facebookresearch.github.io/vrs/
- Current blocker file: `pyvrs_writer/src/vrs_writer.cpp:65-84, 21-28`
- Work plan: `docs/work_plan_rosbag_to_vrs_nov19_2025.md`
- Failing tests: `tests/test_vrs_reader.py` (4/8 failing)
