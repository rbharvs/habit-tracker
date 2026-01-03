# Research: Client-Side Behavior Regression Testing for Backend Refactors

**Date**: 2026-01-03T19:39:24Z
**Git Commit**: 9e11e630a64d003ca40fb6ec511b870751ce5a35
**Branch**: main

## Research Question

How to ensure client-side observable behavior does not change during a major backend refactor through automated testing, with secondary goals of performance, determinism, and maintainability.

## Summary

For ensuring client-side observable behavior remains stable during backend refactors, a multi-layered testing approach is recommended:

1. **HTTP Response Snapshot Testing** (Primary): Use **Syrupy** to snapshot HTTP responses (both JSON and HTML) from FastAPI's TestClient. This catches any change in response content.

2. **Determinism Infrastructure**: Use **time-machine** for time freezing, **unittest.mock** for UUID mocking, and **tmp_path** for isolated test data.

3. **HTML Structure Validation**: Use **BeautifulSoup** for parsing and asserting on HTML structure, particularly HTMX attributes.

4. **E2E Testing** (Optional but valuable): Use **Playwright** for true browser-based testing, visual regression via screenshots, and HTMX interaction testing.

5. **Contract Testing** (Optional): Use **Schemathesis** for OpenAPI property-based testing.

---

## Detailed Findings

### 1. Syrupy Snapshot Testing (Recommended Primary Approach)

**Library**: [syrupy-project/syrupy](https://github.com/syrupy-project/syrupy)
**Installation**: `uv add --dev syrupy`

Syrupy is a pytest plugin that enables snapshot testing with three core principles:
- **Extensible**: Easy to add support for custom data types
- **Idiomatic**: Natural pytest integration (`assert x == snapshot`)
- **Soundness**: Fails if snapshot doesn't exist (not just on differences)

#### Basic Usage

```python
def test_get_habits(client, snapshot):
    response = client.get("/habits")
    assert response.json() == snapshot
```

#### HTML Snapshot Testing with Custom Extension

For testing HTML responses (critical for HTMX):

```python
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode

class HTMLSnapshotExtension(SingleFileSnapshotExtension):
    _write_mode = WriteMode.TEXT
    file_extension = "html"

@pytest.fixture
def snapshot_html(snapshot):
    return snapshot.use_extension(HTMLSnapshotExtension)

def test_index_page(client, snapshot_html):
    response = client.get("/")
    assert response.text == snapshot_html
```

#### Handling Dynamic Values

**Option 1: Matchers (path_type)**
```python
from syrupy.matchers import path_type
from datetime import datetime

def test_create_habit(client, snapshot):
    response = client.post("/habits", json={"name": "Test"})
    assert response.json() == snapshot(
        matcher=path_type({
            "id": (str,),
            "created_at": (str,),
        })
    )
```

**Option 2: Filters (exclude paths)**
```python
from syrupy.filters import paths

def test_api_response(client, snapshot):
    response = client.get("/habits")
    assert response.json() == snapshot(
        exclude=paths("id", "created_at", "updated_at")
    )
```

**Option 3: Deterministic Fixtures (Recommended)**
Make tests fully deterministic by mocking time and UUIDs:
```python
@pytest.fixture
def frozen_time():
    with time_machine.travel("2024-01-15 10:00:00", tick=False):
        yield

@pytest.fixture
def mock_uuid(monkeypatch):
    counter = [0]
    def next_uuid():
        counter[0] += 1
        return uuid.UUID(f"00000000-0000-0000-0000-{counter[0]:012d}")
    monkeypatch.setattr("habit_tracker.storage.uuid.uuid4", next_uuid)
```

#### Snapshot Storage Structure

```
tests/
  __snapshots__/
    test_main/
      test_index_page.html
      test_get_habits.json
  test_main.py
```

#### CLI Commands

```bash
pytest                          # Run tests, fail on snapshot differences
pytest --snapshot-update        # Update snapshots and delete unused
pytest --snapshot-warn-unused   # Warn instead of fail on unused
```

#### CI/CD Integration

- Never use `--snapshot-update` in CI
- Commit `__snapshots__` directory to version control
- Review snapshot changes in PRs like code changes

---

### 2. Insta Patterns (Transferable Concepts)

Key patterns from Rust's insta library that apply to Python:

#### Redaction Strategies

1. **Path-based redactions**: Replace values at specific JSON paths with placeholders
2. **Type-based redactions**: Replace all values of a type (e.g., all datetimes)
3. **Regex filters**: Pattern-based replacement for serialized output

#### Two-Phase Workflow

1. Run tests → creates `.snap.new` files for failures
2. Review changes → interactive or batch accept/reject
3. Commit approved changes

#### Environment Variable Control

| Variable | Description |
|----------|-------------|
| `SNAPSHOT_UPDATE=auto` | `no` in CI, `new` otherwise |
| `SNAPSHOT_UPDATE=always` | Update snapshots immediately |
| `SNAPSHOT_UPDATE=no` | Never write, just run tests |

---

### 3. Real-World Example: claude-code-transcripts

The [simonw/claude-code-transcripts](https://github.com/simonw/claude-code-transcripts) project demonstrates practical snapshot testing patterns:

**Approach**:
- Uses Syrupy with custom `SingleFileSnapshotExtension` for `.html` files
- Stores each snapshot as a separate, human-readable HTML file
- Uses deterministic fixtures with hardcoded timestamps and IDs
- Tests both full page generation and individual component rendering

**Directory Structure**:
```
tests/
  __snapshots__/
    test_generate_html/
      TestGenerateHtml.test_generates_index_html.html
      TestRenderFunctions.test_render_bash_tool.html
```

**Key Pattern - Deterministic Fixtures**:
```python
# tests/sample_session.json - All timestamps and IDs are hardcoded
{
  "loglines": [
    {
      "type": "user",
      "timestamp": "2025-12-24T10:00:00.000Z",  # Fixed
      "message": {"content": "Create a function", "role": "user"}
    }
  ]
}
```

---

### 4. Playwright E2E Testing

**Library**: [microsoft/playwright-python](https://github.com/microsoft/playwright-python)
**Installation**: `uv add --dev playwright pytest-playwright && playwright install`

Playwright provides true browser-based testing, valuable for:
- Visual regression via screenshot comparison
- HTMX interaction testing
- Complex user flow validation

#### Visual Regression Testing

```python
async def test_habits_page_visual(page):
    await page.goto("http://localhost:8000/")
    await expect(page).to_have_screenshot("habits-page.png")
```

**Configuration Options**:
- `maxDiffPixelRatio`: Acceptable percentage of different pixels (0-1)
- `threshold`: Color difference tolerance (0 = strict)
- `mask`: Selectors to exclude from comparison

#### HTMX Testing Strategies

```python
async def test_htmx_interaction(page):
    await page.goto("http://localhost:8000/")

    # Wait for HTMX to be ready
    await page.wait_for_function("window.htmx !== undefined")

    # Click and wait for HTMX request to complete
    await page.click('[hx-post="/save"]')
    await expect(page.locator('.htmx-request')).to_have_count(0)

    # Verify result
    await expect(page.locator('.saved-indicator')).to_be_visible()
```

#### HAR Recording for Deterministic API Responses

```python
# Record HAR file (first run)
await page.route_from_har("fixtures/api.har", update=True)

# Replay from HAR (subsequent runs)
await page.route_from_har("fixtures/api.har")
```

#### Trace Files for Debugging

```python
# Enable tracing in conftest.py
@pytest.fixture
async def traced_page(browser):
    context = await browser.new_context()
    await context.tracing.start(screenshots=True, snapshots=True)
    page = await context.new_page()
    yield page
    await context.tracing.stop(path="trace.zip")
```

View with: `playwright show-trace trace.zip`

#### Performance: Parallel Execution

```bash
pytest tests/e2e/ --numprocesses auto  # Uses pytest-xdist
```

---

### 5. Determinism Techniques

#### Time Mocking

**Recommended: time-machine** (100-200x faster than freezegun)
```python
import time_machine

@pytest.fixture
def frozen_time():
    with time_machine.travel("2024-01-15 10:00:00", tick=False) as t:
        yield t

def test_today_entries(client, frozen_time):
    response = client.get("/")
    assert "Jan 15" in response.text
```

**Alternative: freezegun** (if PyPy support needed)
```python
from freezegun import freeze_time

@freeze_time("2024-01-15 10:00:00")
def test_today_entries(client):
    response = client.get("/")
    assert "Jan 15" in response.text
```

#### UUID Mocking

```python
from unittest.mock import patch
import uuid

@pytest.fixture
def mock_uuid(monkeypatch):
    counter = [0]
    def next_uuid():
        counter[0] += 1
        return uuid.UUID(f"00000000-0000-0000-0000-{counter[0]:012d}")
    monkeypatch.setattr("uuid.uuid4", next_uuid)
```

#### File System Isolation

```python
@pytest.fixture
def test_storage(tmp_path, monkeypatch):
    """Isolated storage for each test."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    # ... create storage instance
```

#### Detecting Order-Dependent Tests

```bash
uv add --dev pytest-randomly
pytest  # Randomizes test order, prints seed for reproduction
pytest --randomly-seed=1234  # Reproduce specific order
```

---

### 6. HTML Assertion Strategies

**Library**: BeautifulSoup4
**Installation**: `uv add --dev beautifulsoup4`

```python
from bs4 import BeautifulSoup

def test_htmx_attributes(client):
    response = client.get("/")
    soup = BeautifulSoup(response.text, "html.parser")

    # Verify HTMX form attributes
    form = soup.select_one("form#habit-form")
    assert form["hx-post"] == "save"
    assert form["hx-target"] == "#save-indicator"

    # Verify habit list structure
    habits = soup.select(".habit-item")
    assert len(habits) == 3

    # Verify checkbox state
    checkbox = soup.select_one("input[name='habit_workout']")
    assert checkbox.has_attr("checked")
```

#### Normalized HTML Comparison

```python
def normalize_html(html: str) -> str:
    """Normalize HTML for consistent snapshots."""
    soup = BeautifulSoup(html, "html.parser")
    return soup.prettify()

def test_index_normalized(client, snapshot_html):
    response = client.get("/")
    assert normalize_html(response.text) == snapshot_html
```

---

### 7. Contract Testing (Optional)

**Library**: Schemathesis
**Installation**: `uv add --dev schemathesis`

Property-based testing against OpenAPI schema:

```python
import schemathesis
from habit_tracker.main import app

schema = schemathesis.openapi.from_asgi("/openapi.json", app)

@schema.parametrize()
def test_api_contract(case):
    case.call_and_validate()
```

Benefits:
- Automatically generates test cases
- Validates response against schema
- Catches spec violations

---

## Recommended Testing Stack for Habit Tracker

### pyproject.toml additions

```toml
[tool.uv]
dev-dependencies = [
    # Existing...
    "syrupy>=5.0.0",           # Snapshot testing
    "time-machine>=2.14",      # Time freezing
    "beautifulsoup4>=4.12",    # HTML parsing
    # Optional
    "playwright>=1.49.0",      # E2E testing
    "pytest-playwright>=0.7.0",
    "schemathesis>=3.32",      # Contract testing
]
```

### Recommended conftest.py

```python
import pytest
import time_machine
from pathlib import Path
from unittest.mock import patch
import uuid
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode

# HTML Snapshot Extension
class HTMLSnapshotExtension(SingleFileSnapshotExtension):
    _write_mode = WriteMode.TEXT
    file_extension = "html"

@pytest.fixture
def snapshot_html(snapshot):
    return snapshot.use_extension(HTMLSnapshotExtension)

# Time freezing
@pytest.fixture
def frozen_time():
    with time_machine.travel("2024-01-15 10:00:00", tick=False) as t:
        yield t

# UUID mocking
@pytest.fixture
def mock_uuid(monkeypatch):
    counter = [0]
    def next_uuid():
        counter[0] += 1
        return uuid.UUID(f"00000000-0000-0000-0000-{counter[0]:012d}")
    monkeypatch.setattr("uuid.uuid4", next_uuid)

# Combined deterministic fixture
@pytest.fixture
def deterministic(frozen_time, mock_uuid):
    """Combine all determinism fixtures."""
    pass
```

### Example Snapshot Test

```python
from bs4 import BeautifulSoup

def test_index_page(client, snapshot_html, deterministic):
    """Snapshot test for index page HTML."""
    response = client.get("/?day=2024-01-15")
    assert response.status_code == 200
    assert response.text == snapshot_html

def test_save_endpoint(client, snapshot, deterministic):
    """Snapshot test for save response."""
    response = client.post(
        "/save",
        data={"date": "2024-01-15", "habit_test": "on"},
        headers={"HX-Request": "true"},
    )
    assert response.text == snapshot

def test_habits_api(client, snapshot, deterministic):
    """Snapshot test for habits JSON."""
    response = client.get("/habits")
    assert response.json() == snapshot
```

---

## Architecture Notes

### Testing Layers for Backend Refactor

| Layer | Tool | Purpose | Speed |
|-------|------|---------|-------|
| HTTP Response Snapshots | Syrupy + TestClient | Catch any response change | Fast (~ms) |
| HTML Structure | BeautifulSoup | Verify DOM structure | Fast |
| Visual Regression | Playwright | Catch CSS/layout issues | Slow (~s) |
| Contract Testing | Schemathesis | Validate API spec | Medium |

### Recommended Strategy

1. **Before refactor**: Generate baseline snapshots for all endpoints
2. **During refactor**: Run snapshot tests after each change
3. **After refactor**: Review any snapshot differences, update intentional changes

### Key Principles

- **Determinism first**: Mock time, UUIDs, and isolate storage before writing snapshots
- **Full response snapshots**: Capture entire HTTP responses, not just fragments
- **Version control snapshots**: Commit `.ambr`/`.html` files alongside tests
- **Review like code**: Treat snapshot diffs in PRs as carefully as code changes

---

## Open Questions

1. **Snapshot granularity**: Should each endpoint have its own snapshot, or group related endpoints?
2. **Dynamic content handling**: Use matchers vs. fully deterministic fixtures?
3. **Playwright scope**: Use for smoke tests only, or comprehensive E2E coverage?
4. **Performance budget**: Maximum acceptable test suite runtime?

---

## Code References

- `tests/test_main.py` - Existing HTTP tests using TestClient
- `tests/test_e2e.py` - Existing E2E test pattern
- `tests/conftest.py` - Existing fixtures including `test_storage`
- `src/habit_tracker/main.py` - All FastAPI routes to test
