# Syrupy Snapshot Testing Library - Research Findings

## Overview

Syrupy is a zero-dependency pytest snapshot testing plugin that enables developers to write tests which assert immutability of computed results. It follows three core principles:

1. **Extensible**: Easy to add support for custom data types
2. **Idiomatic**: Natural pytest integration (`assert x == snapshot`)
3. **Soundness**: Fails test suite if snapshot does not exist (not just on differences)

**Repository**: https://github.com/syrupy-project/syrupy
**License**: MIT
**Python**: >=3.10 (for v5.x.x)
**Pytest**: >=8, <9

---

## 1. Core Concepts and Architecture

### File Structure

```
src/syrupy/
  __init__.py          # Pytest plugin hooks and fixture definition
  assertion.py         # SnapshotAssertion class - core comparison logic
  session.py           # SnapshotSession - manages test run state
  data.py              # Data structures: Snapshot, SnapshotCollection
  report.py            # SnapshotReport - generates test summary
  types.py             # Type definitions
  filters.py           # Built-in property filters (paths, props)
  matchers.py          # Built-in matchers (path_type, path_value)
  extensions/
    base.py            # Abstract base classes
    amber/             # Default Amber serializer
    json/              # JSON extension
    single_file.py     # One-file-per-snapshot extensions
    image.py           # PNG/SVG extensions
```

### Key Components

#### 1. SnapshotAssertion (`/tmp/syrupy/src/syrupy/assertion.py`)
The main fixture class that handles:
- Serialization of test data
- Comparison with stored snapshots
- Recording assertion results
- Tracking multiple assertions per test

```python
@dataclass(eq=False, order=False, repr=False)
class SnapshotAssertion:
    session: "SnapshotSession"
    extension_class: type["AbstractSyrupyExtension"]
    test_location: "PyTestLocation"
    update_snapshots: bool
    include: Optional["PropertyFilter"] = None
    exclude: Optional["PropertyFilter"] = None
    matcher: Optional["PropertyMatcher"] = None
```

The `__eq__` method is overridden to perform snapshot comparison:
```python
def __eq__(self, other: "SerializableData") -> bool:
    return self._assert(other)
```

#### 2. SnapshotSession (`/tmp/syrupy/src/syrupy/session.py`)
Manages the overall test session:
- Tracks collected and selected test items
- Buffers snapshot writes in memory for performance
- Handles unused snapshot detection and removal
- Coordinates with pytest hooks

#### 3. AbstractSyrupyExtension (`/tmp/syrupy/src/syrupy/extensions/base.py`)
Base class combining four responsibilities:
- `SnapshotSerializer`: Converts data to string format
- `SnapshotCollectionStorage`: Manages file I/O
- `SnapshotReporter`: Generates diff output
- `SnapshotComparator`: Compares serialized data

---

## 2. How Snapshot Tests Are Written

### Basic Usage

```python
def test_foo(snapshot):
    actual = "Some computed value!"
    assert actual == snapshot
```

### Multiple Assertions Per Test

```python
def test_multiple(snapshot):
    assert "First." == snapshot      # Named: test_multiple
    assert "Second." == snapshot     # Named: test_multiple.1
    assert "Third." == snapshot      # Named: test_multiple.2
```

### Custom Snapshot Names

```python
def test_case(snapshot):
    assert "actual" == snapshot(name="case_a")
    assert "other" == snapshot(name="case_b")
```

### Using Different Extensions

```python
from syrupy.extensions.json import JSONSnapshotExtension

@pytest.fixture
def snapshot_json(snapshot):
    return snapshot.use_extension(JSONSnapshotExtension)

def test_api_call(client, snapshot_json):
    resp = client.post("/endpoint")
    assert resp.json() == snapshot_json
```

### unittest.TestCase Compatibility

```python
class MyTest(TestCase):
    @pytest.fixture(autouse=True)
    def setupSnapshot(self, snapshot):
        self.snapshot = snapshot

    def test_foo(self):
        assert "value" == self.snapshot
```

---

## 3. Snapshot Storage Format

### Directory Structure

By default, snapshots are stored in `__snapshots__` directory adjacent to test files:

```
tests/
  test_foo.py
  __snapshots__/
    test_foo.ambr           # Amber format (default)
tests/api/
  test_endpoints.py
  __snapshots__/
    test_endpoints/         # For single-file extensions
      test_get_user.json    # One file per test
```

### Amber Format (`.ambr`)

The default serialization format (`/tmp/syrupy/src/syrupy/extensions/amber/serializer.py`):

```
# serializer version: 1
# name: test_foo
  'Some computed value!'
# ---
# name: test_bar
  dict({
    'key': 'value',
    'nested': dict({
      'a': 1,
      'b': 2,
    }),
  })
# ---
```

**Features**:
- Version header for migration support
- Human-readable Python-like syntax
- Multi-line strings use triple quotes
- Sorted dictionary keys for determinism
- Handles cycles with ellipsis (`...`)
- Newlines normalized to `\n` for cross-platform compatibility

### JSON Format (`.json`)

Single-file extension storing one snapshot per file:

```json
{
  "key": "value",
  "nested": {
    "a": 1,
    "b": 2
  }
}
```

### Single-File Extensions

For binary data or per-test-file organization:
- `SingleFileSnapshotExtension`: Raw bytes (`.raw`)
- `SingleFileAmberSnapshotExtension`: Amber format, one file per test
- `PNGImageSnapshotExtension`: PNG images (`.png`)
- `SVGImageSnapshotExtension`: SVG images (`.svg`)

---

## 4. Snapshot Updates

### CLI Options

```bash
pytest --snapshot-update           # Update snapshots and delete unused
pytest --snapshot-warn-unused      # Warn instead of fail on unused
pytest --snapshot-details          # Show detailed report of changes
pytest --snapshot-diff-mode        # "detailed" or "disabled"
pytest --snapshot-dirname          # Custom directory name (default: __snapshots__)
```

### Update Flow

1. Run tests normally - fails if snapshots missing or different
2. Run with `--snapshot-update` to create/update snapshots
3. Commit `__snapshots__` directory to version control

### Unused Snapshot Detection

Syrupy tracks which snapshots are used during a test run:
- If `--snapshot-update`: unused snapshots are deleted
- Otherwise: test suite fails with list of unused snapshots
- Respects test selection (`-k`, path filters, etc.)

---

## 5. Available Serializers

### AmberDataSerializer (Default)

Location: `/tmp/syrupy/src/syrupy/extensions/amber/serializer.py`

```python
class AmberDataSerializer:
    VERSION = "1"
    _indent: str = "  "
    _max_depth: int = 99
```

**Supported Types**:
- Primitives: str, int, float, bool, None
- Collections: list, tuple, set, frozenset, dict, OrderedDict
- Named tuples
- Functions (signature serialization)
- Custom objects (via `__repr__` or attribute introspection)

**Sorting**:
- Dictionary keys are sorted by default
- Sets are sorted
- `AmberDataSerializerSorted` variant sorts snapshot names numerically

### JSONSnapshotExtension

Location: `/tmp/syrupy/src/syrupy/extensions/json/__init__.py`

```python
class JSONSnapshotExtension(SingleFileSnapshotExtension):
    _max_depth: int = 99
    _write_mode = WriteMode.TEXT
    file_extension = "json"
```

**Features**:
- Outputs pretty-printed JSON with 2-space indent
- Handles datetime formatting
- Converts custom objects to repr strings
- Non-string dict keys are skipped (JSON limitation)

---

## 6. Determinism Features

### Filtering Properties

**Exclude specific properties** (`/tmp/syrupy/src/syrupy/filters.py`):

```python
from syrupy.filters import paths, props

# Exclude by exact path
assert data == snapshot(exclude=paths("id", "created_at", "nested.timestamp"))

# Exclude by property name anywhere
assert data == snapshot(exclude=props("id", "timestamp"))
```

**Include only specific properties**:

```python
from syrupy.filters import paths_include

# Must include parent paths for nested values
assert data == snapshot(include=paths_include(["name"], ["nested", "value"]))
```

### Matchers for Dynamic Values

**path_type matcher** (`/tmp/syrupy/src/syrupy/matchers.py`):

```python
from syrupy.matchers import path_type

# Replace dynamic values with type placeholders
matcher = path_type({
    "date_created": (datetime,),
    "nested.id": (int,),
}, types=(uuid.UUID,))

assert data == snapshot(matcher=matcher)
```

Result in snapshot:
```python
dict({
  'date_created': datetime,
  'id': int,
  'some_uuid': UUID,
})
```

**Custom replacer**:

```python
matcher = path_type(
    {"timestamp": (datetime,)},
    replacer=lambda data, _: "TIMESTAMP_PLACEHOLDER"
)
```

**Regex path matching**:

```python
matcher = path_type(
    {r"data\.list\..*\.id": (int,)},
    regex=True
)
```

**Composing matchers**:

```python
from syrupy.matchers import compose_matchers, path_type

matcher = compose_matchers(
    path_type(types=(int, float), replacer=lambda *_: "NUMBER"),
    path_type(types=(datetime,), replacer=lambda *_: "DATETIME"),
)
```

### Serialization Determinism

The Amber serializer ensures determinism through:
1. **Sorted dictionary keys**: `sorted(data.keys())`
2. **Sorted set elements**: `sorted(data)`
3. **Normalized newlines**: `\r\n` and `\r` converted to `\n`
4. **Cycle detection**: Prevents infinite loops, shows `...`
5. **Max depth limiting**: Prevents stack overflow

---

## 7. Performance Characteristics

### Benchmarks

Location: `/tmp/syrupy/benchmarks/test_1000x.py`

Tests:
- `test_1000x_reads`: 1000 parameterized assertions (read performance)
- `test_1000x_writes`: 1000 snapshots with `--snapshot-update`

### Optimizations

1. **Buffered writes** (`session.py`):
   ```python
   _queued_snapshot_writes: defaultdict[
       _QueuedWriteExtensionKey,
       dict[_QueuedWriteTestLocationKey, "SerializedData"],
   ]
   ```
   Writes are batched per file location, written once at session end.

2. **Cached reads** (`amber/__init__.py`):
   ```python
   @classmethod
   @lru_cache
   def __cacheable_read_snapshot(cls, snapshot_location: str, cache_key: str):
   ```
   Snapshot files are read once per session and cached.

3. **Quick diff** (`utils.py`):
   - Limits diff output to prevent slowdowns with large snapshots
   - Can disable diff entirely with `--snapshot-diff-mode=disabled`

### Performance Tips

1. Use `--snapshot-diff-mode=disabled` for very large snapshots
2. Consider single-file extensions to reduce I/O
3. Exclude unnecessary large/dynamic data from snapshots

---

## 8. CI/CD Integration Patterns

### GitHub Actions Example

From `/tmp/syrupy/.github/workflows/ci.yaml`:

```yaml
jobs:
  tests:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest]
        python-version: ['3.10', '3.11', '3.12', '3.13']
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
      - name: Run Tests
        run: pytest
```

### CI Best Practices

1. **Never use `--snapshot-update` in CI** - snapshots should be committed
2. **Test both platforms** - snapshots are cross-platform compatible
3. **Fail on unused snapshots** - default behavior catches stale tests
4. **Use `--snapshot-warn-unused`** only during transitions

### pytest-xdist Limitations

From `/tmp/syrupy/src/syrupy/session.py`:
```python
if is_xdist_worker():
    # Unused snapshot removal is disabled with xdist
    return exitstatus
```

When using `pytest-xdist`:
- Read operations work normally
- Unused snapshot detection is disabled with multiple workers
- See [issue #535](https://github.com/syrupy-project/syrupy/issues/535)

---

## 9. Best Practices for Large Snapshot Suites

### 1. Organize Snapshots by Feature

```
tests/api/__snapshots__/test_users.ambr
tests/api/__snapshots__/test_posts.ambr
tests/models/__snapshots__/test_user_model.ambr
```

### 2. Use Custom Snapshot Directories

```python
class FeatureSpecificExtension(AmberSnapshotExtension):
    snapshot_dirname = "__feature_snapshots__"
```

### 3. Use Named Snapshots for Clarity

```python
def test_user_serialization(snapshot):
    assert User(name="Alice").to_dict() == snapshot(name="alice")
    assert User(name="Bob").to_dict() == snapshot(name="bob")
```

### 4. Exclude Non-Deterministic Data

```python
@pytest.fixture
def snapshot_api(snapshot):
    return snapshot.with_defaults(
        exclude=paths("id", "created_at", "updated_at", "request_id"),
        matcher=path_type({"timestamp": (datetime,)})
    )
```

### 5. Review Snapshot Changes in PRs

- Treat snapshot changes like code changes
- Ensure changes are intentional
- Consider adding `--snapshot-details` output to CI logs

### 6. Clean Up Unused Snapshots Regularly

```bash
# Run locally before committing
pytest --snapshot-update
```

### 7. Custom Serializers for Complex Objects

```python
class MyObject:
    def __repr__(self) -> str:
        return f"MyObject(field1={self.field1}, field2={self.field2})"
```

Or use the amber helper:
```python
from syrupy.extensions.amber import AmberDataSerializer

def test_custom_object(snapshot):
    obj = MyComplexObject()
    assert AmberDataSerializer.object_as_named_tuple(obj) == snapshot
```

### 8. Type-Specific Extensions

```python
from syrupy.extensions.json import JSONSnapshotExtension

@pytest.fixture
def snapshot_json(snapshot):
    return snapshot.use_extension(JSONSnapshotExtension)

def test_api_response(client, snapshot_json):
    response = client.get("/api/users")
    assert response.json() == snapshot_json
```

---

## 10. Creating Custom Extensions

### Custom Snapshot Directory

```python
from syrupy.extensions.amber import AmberSnapshotExtension

class CustomDirExtension(AmberSnapshotExtension):
    snapshot_dirname = "__custom_snapshots__"

@pytest.fixture
def snapshot(snapshot):
    return snapshot.use_extension(CustomDirExtension)
```

### Custom Serializer

```python
from syrupy.extensions.amber import AmberSnapshotExtension

class SortedExtension(AmberSnapshotExtension):
    @classmethod
    def serialize(cls, data, **kwargs):
        # Custom serialization logic
        return super().serialize(data, **kwargs)
```

### Custom File Extension

```python
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode

class YAMLSnapshotExtension(SingleFileSnapshotExtension):
    file_extension = "yaml"
    _write_mode = WriteMode.TEXT

    def serialize(self, data, **kwargs):
        import yaml
        return yaml.dump(data, default_flow_style=False)
```

---

## Key File References

| File | Purpose |
|------|---------|
| `/tmp/syrupy/src/syrupy/__init__.py` | Pytest plugin hooks, `snapshot` fixture |
| `/tmp/syrupy/src/syrupy/assertion.py` | `SnapshotAssertion` class, comparison logic |
| `/tmp/syrupy/src/syrupy/session.py` | `SnapshotSession`, test run management |
| `/tmp/syrupy/src/syrupy/extensions/base.py` | `AbstractSyrupyExtension` base class |
| `/tmp/syrupy/src/syrupy/extensions/amber/serializer.py` | `AmberDataSerializer` |
| `/tmp/syrupy/src/syrupy/extensions/json/__init__.py` | `JSONSnapshotExtension` |
| `/tmp/syrupy/src/syrupy/filters.py` | `paths()`, `props()`, `paths_include()` |
| `/tmp/syrupy/src/syrupy/matchers.py` | `path_type()`, `path_value()`, `compose_matchers()` |
| `/tmp/syrupy/src/syrupy/report.py` | `SnapshotReport`, unused detection |
| `/tmp/syrupy/tests/examples/` | Example custom extensions |
