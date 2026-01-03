# Implementation Plan: Client-Behavior Regression Testing Suite

**Date**: 2026-01-03T19:50:27Z
**Git Commit**: 9e11e630a64d003ca40fb6ec511b870751ce5a35
**Branch**: main

## Overview

Add a client-behavior regression testing suite using Syrupy snapshot testing to ensure HTTP responses (HTML structure, JSON payloads, HTMX attributes) remain stable during backend refactors. This complements existing functional tests by capturing the exact response content that clients depend on.

## Current State

### Existing Test Infrastructure

**conftest.py** (`tests/conftest.py:1-18`):
- `test_storage` fixture: Creates isolated `JsonFileStorage` using `tmp_path`
- Overrides FastAPI dependency: `app.dependency_overrides[get_storage] = lambda: test_storage`
- No time mocking, UUID mocking, or determinism fixtures

**Test Files**:
| File | Lines | Purpose |
|------|-------|---------|
| `test_main.py` | 1350 | Route testing with string assertions |
| `test_e2e.py` | 30 | Minimal E2E workflow (1 test) |
| `test_models.py` | 518 | Pydantic model validation |
| `test_storage.py` | 271 | Storage layer operations |
| `test_colors.py` | 104 | Color utility functions |
| `test_handler.py` | 129 | Lambda handler |
| `test_protocol.py` | 58 | Storage protocol |

**Current Dev Dependencies** (`pyproject.toml:19-26`):
```toml
[tool.uv]
dev-dependencies = [
    "httpx>=0.28.1",
    "moto[dynamodb]>=5.0.0",
    "pytest>=9.0.2",
    "ruff>=0.14.10",
    "ty>=0.0.7",
]
```

### Routes to Test (11 total)

| Method | Path | Response Type | HTMX Behavior |
|--------|------|---------------|---------------|
| GET | `/` | HTML page (`index.html`) | Full page |
| POST | `/save` | HTML partial or redirect | HTMX: saved indicator |
| GET | `/habits` | HTML page (`habits.html`) | Full page |
| POST | `/habits` | Redirect with HX-Redirect | Creates habit |
| DELETE | `/habits/{id}` | HTML partial or redirect | HTMX: updated list |
| POST | `/habits/reorder` | HTML partial or redirect | HTMX: updated list |
| GET | `/habits/{id}/edit` | HTML page (`edit_habit.html`) | Full page |
| PUT | `/habits/{id}` | "Saved" or redirect | HTMX: plain text |
| GET | `/calendar` | Redirect or HTML | Redirects to first habit |
| GET | `/calendar/{id}` | HTML page (`calendar.html`) | Full page |
| GET | `/habits/{id}/entry-count` | JSON `{count: int}` | API only |

### Critical HTMX Attributes

From template analysis, these attributes must be preserved:

- `hx-post="save"` on index form → `#save-status`
- `hx-post="habits"` on create form → `#habit-list`
- `hx-put="../{{ habit.id }}"` on edit form → `#save-status`
- `hx-delete="habits/{{ habit.id }}"` → `#habit-list`
- `hx-confirm` messages on archive buttons
- `data-habit-id`, `data-habit-type`, `data-id` attributes

## Desired End State

1. **Snapshot coverage for all endpoints**: Every route has at least one snapshot test capturing the response
2. **Deterministic fixtures**: `frozen_time` and `mock_uuid` fixtures ensure reproducible snapshots
3. **Custom HTML extension**: Store HTML snapshots as `.html` files for readable diffs
4. **HTMX validation helpers**: justhtml assertions for critical HTMX attributes
5. **Organized test structure**: Dedicated `tests/test_snapshots.py` file

### Verification

```bash
# All tests pass with deterministic snapshots
make test

# Snapshot files exist and are tracked
ls tests/__snapshots__/test_snapshots/*.html

# Update workflow works
uv run pytest tests/test_snapshots.py --snapshot-update
```

## What We're NOT Doing

- **Playwright E2E testing** - Deferred to later phase
- **Schemathesis contract testing** - Deferred to later phase
- **Visual regression testing** - Out of scope
- **Screenshot comparison** - Out of scope
- **JavaScript behavior testing** - Snapshot tests focus on HTML structure only
- **Replacing existing tests** - Snapshots complement, not replace, `test_main.py`

## Implementation Approach

1. Add dependencies: `syrupy`, `time-machine`, `justhtml`
2. Create determinism fixtures in `conftest.py`
3. Create custom HTML snapshot extension
4. Write snapshot tests organized by route category
5. Add HTMX attribute validation helpers (using justhtml for HTML parsing)

---

## Phase 1: Dependencies and Fixtures

### Overview
Add required dependencies and create determinism infrastructure in `conftest.py`.

### Changes Required

#### Add Dependencies

**Command**:
```bash
uv add --dev syrupy time-machine justhtml
```

**Result in pyproject.toml**:
```toml
[tool.uv]
dev-dependencies = [
    "httpx>=0.28.1",
    "justhtml>=1.0.0",
    "moto[dynamodb]>=5.0.0",
    "pytest>=9.0.2",
    "ruff>=0.14.10",
    "syrupy>=5.0.0",
    "time-machine>=2.14",
    "ty>=0.0.7",
]
```

#### Update conftest.py

**File**: `tests/conftest.py`
**Changes**: Add imports and new fixtures after existing code

```python
# Add these imports at top
import time_machine
import uuid
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode


# Custom HTML snapshot extension for readable .html files
class HTMLSnapshotExtension(SingleFileSnapshotExtension):
    _write_mode = WriteMode.TEXT
    _file_extension = "html"


@pytest.fixture
def snapshot_html(snapshot):
    """Snapshot fixture that stores HTML as .html files."""
    return snapshot.use_extension(HTMLSnapshotExtension)


@pytest.fixture
def frozen_time():
    """Freeze time to a deterministic value for snapshot tests."""
    with time_machine.travel("2025-01-15 10:30:00", tick=False) as t:
        yield t


@pytest.fixture
def mock_uuid(monkeypatch):
    """Generate predictable UUIDs for snapshot tests."""
    counter = [0]

    def next_uuid():
        counter[0] += 1
        return uuid.UUID(f"00000000-0000-0000-0000-{counter[0]:012d}")

    # Patch both possible import locations
    monkeypatch.setattr("uuid.uuid4", next_uuid)
    return next_uuid


@pytest.fixture
def deterministic(frozen_time, mock_uuid, test_storage):
    """Combined fixture for fully deterministic snapshot tests."""
    pass


@pytest.fixture
def client():
    """TestClient fixture for consistent usage across tests."""
    from starlette.testclient import TestClient
    from habit_tracker.main import app
    return TestClient(app)
```

### Success Criteria

#### Automated Verification:
- [x] `uv sync` completes without errors
- [x] `make fix` passes (linting, formatting, type checking)
- [x] `make test` passes (existing tests still work)

#### Manual Verification:
- [x] `import time_machine` works in Python REPL
- [x] `from syrupy import snapshot` works in Python REPL
- [x] `from justhtml import JustHTML` works in Python REPL

---

## Phase 2: Snapshot Tests for GET Routes

### Overview
Create snapshot tests for all GET routes that return HTML pages.

### Changes Required

#### Create test_snapshots.py

**File**: `tests/test_snapshots.py`

```python
"""Snapshot tests for HTTP response regression testing.

These tests capture the exact HTML/JSON responses to detect unintended changes
during refactoring. Run `pytest --snapshot-update` to update snapshots after
intentional changes.
"""

from datetime import date

import pytest
from starlette.testclient import TestClient

from habit_tracker.main import app
from habit_tracker.models import (
    BinaryEntry,
    BinaryHabit,
    DailyEntries,
    JournalEntry,
    JournalHabit,
    SingleSelectEntry,
    SingleSelectHabit,
)


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def sample_habits(test_storage):
    """Create a representative set of habits for snapshot tests."""
    habits = [
        BinaryHabit(id="workout", name="Did you work out?"),
        SingleSelectHabit(
            id="mood",
            name="How was your mood?",
            options=["Great", "Good", "Okay", "Bad"],
        ),
        JournalHabit(id="notes", name="Daily notes"),
    ]
    test_storage.save_habits(habits)
    return habits


@pytest.fixture
def sample_entries(test_storage, sample_habits):
    """Create sample entries for the test date."""
    entries = DailyEntries(
        date=date(2025, 1, 15),
        entries={
            "workout": BinaryEntry(value=True),
            "mood": SingleSelectEntry(value="Good"),
            "notes": JournalEntry(value="Test journal entry for snapshot."),
        },
    )
    test_storage.save_entries(entries)
    return entries


# =============================================================================
# Index Page Snapshots
# =============================================================================


class TestIndexPageSnapshots:
    """Snapshot tests for the daily entry form (GET /)."""

    def test_index_empty_state(
        self, test_storage, deterministic, snapshot_html, client
    ):
        """Index page with no habits shows empty state."""
        response = client.get("/?day=2025-01-15")
        assert response.status_code == 200
        assert response.text == snapshot_html

    def test_index_with_habits_no_entries(
        self, sample_habits, deterministic, snapshot_html, client
    ):
        """Index page with habits but no entries for the day."""
        response = client.get("/?day=2025-01-15")
        assert response.status_code == 200
        assert response.text == snapshot_html

    def test_index_with_entries(
        self, sample_entries, deterministic, snapshot_html, client
    ):
        """Index page with existing entries filled in."""
        response = client.get("/?day=2025-01-15")
        assert response.status_code == 200
        assert response.text == snapshot_html


# =============================================================================
# Habits Management Page Snapshots
# =============================================================================


class TestHabitsPageSnapshots:
    """Snapshot tests for the habit management page (GET /habits)."""

    def test_habits_empty_state(
        self, test_storage, deterministic, snapshot_html, client
    ):
        """Habits page with no habits shows empty state."""
        response = client.get("/habits")
        assert response.status_code == 200
        assert response.text == snapshot_html

    def test_habits_with_active_habits(
        self, sample_habits, deterministic, snapshot_html, client
    ):
        """Habits page listing active habits."""
        response = client.get("/habits")
        assert response.status_code == 200
        assert response.text == snapshot_html

    def test_habits_with_archived(
        self, sample_habits, test_storage, deterministic, snapshot_html, client
    ):
        """Habits page with mix of active and archived habits."""
        habits = test_storage.load_habits()
        habits[0].archived = True  # Archive the first habit
        test_storage.save_habits(habits)

        response = client.get("/habits")
        assert response.status_code == 200
        assert response.text == snapshot_html


# =============================================================================
# Edit Habit Page Snapshots
# =============================================================================


class TestEditHabitPageSnapshots:
    """Snapshot tests for the habit edit form (GET /habits/{id}/edit)."""

    def test_edit_binary_habit(
        self, sample_habits, deterministic, snapshot_html, client
    ):
        """Edit form for a binary habit."""
        response = client.get("/habits/workout/edit")
        assert response.status_code == 200
        assert response.text == snapshot_html

    def test_edit_single_select_habit(
        self, sample_habits, deterministic, snapshot_html, client
    ):
        """Edit form for a single-select habit with options."""
        response = client.get("/habits/mood/edit")
        assert response.status_code == 200
        assert response.text == snapshot_html

    def test_edit_journal_habit(
        self, sample_habits, deterministic, snapshot_html, client
    ):
        """Edit form for a journal habit."""
        response = client.get("/habits/notes/edit")
        assert response.status_code == 200
        assert response.text == snapshot_html


# =============================================================================
# Calendar Page Snapshots
# =============================================================================


class TestCalendarPageSnapshots:
    """Snapshot tests for the calendar view (GET /calendar/{id})."""

    def test_calendar_empty_month(
        self, sample_habits, deterministic, snapshot_html, client
    ):
        """Calendar view with no entries for the month."""
        response = client.get("/calendar/workout?year=2025&month=1")
        assert response.status_code == 200
        assert response.text == snapshot_html

    def test_calendar_with_entries(
        self, sample_entries, deterministic, snapshot_html, client
    ):
        """Calendar view with entries showing colored cells."""
        response = client.get("/calendar/workout?year=2025&month=1")
        assert response.status_code == 200
        assert response.text == snapshot_html

    def test_calendar_single_select_with_legend(
        self, sample_entries, deterministic, snapshot_html, client
    ):
        """Calendar for single-select habit shows color legend."""
        response = client.get("/calendar/mood?year=2025&month=1")
        assert response.status_code == 200
        assert response.text == snapshot_html


# =============================================================================
# JSON API Snapshots
# =============================================================================


class TestAPISnapshots:
    """Snapshot tests for JSON API endpoints."""

    def test_entry_count_empty(
        self, sample_habits, deterministic, snapshot, client
    ):
        """Entry count returns zero when no entries exist."""
        response = client.get("/habits/workout/entry-count")
        assert response.status_code == 200
        assert response.json() == snapshot

    def test_entry_count_with_entries(
        self, sample_entries, deterministic, snapshot, client
    ):
        """Entry count returns correct count."""
        response = client.get("/habits/workout/entry-count")
        assert response.status_code == 200
        assert response.json() == snapshot
```

### Success Criteria

#### Automated Verification:
- [x] `make test` passes
- [x] `uv run pytest tests/test_snapshots.py -v` runs all snapshot tests
- [x] Snapshot files created in `tests/__snapshots__/test_snapshots/`

#### Manual Verification:
- [x] HTML snapshot files are readable and well-formatted
- [x] `git diff` shows snapshot files as new additions

---

## Phase 3: Snapshot Tests for POST/PUT/DELETE Routes

### Overview
Add snapshot tests for state-modifying routes, testing both HTMX and non-HTMX response paths.

### Changes Required

#### Extend test_snapshots.py

**File**: `tests/test_snapshots.py`
**Changes**: Add new test classes after existing code

```python
# =============================================================================
# Save Endpoint Snapshots (POST /save)
# =============================================================================


class TestSaveEndpointSnapshots:
    """Snapshot tests for the entry save endpoint (POST /save)."""

    def test_save_htmx_response(
        self, sample_habits, deterministic, snapshot_html, client
    ):
        """HTMX save returns saved indicator HTML."""
        response = client.post(
            "/save",
            data={"date": "2025-01-15", "habit_workout": "on"},
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200
        assert response.text == snapshot_html

    def test_save_non_htmx_redirect(
        self, sample_habits, deterministic, client
    ):
        """Non-HTMX save returns redirect (not snapshotted, just verify behavior)."""
        response = client.post(
            "/save",
            data={"date": "2025-01-15", "habit_workout": "on"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "day=2025-01-15" in response.headers["location"]


# =============================================================================
# Habit CRUD Snapshots
# =============================================================================


class TestHabitCRUDSnapshots:
    """Snapshot tests for habit create/update/delete operations."""

    def test_create_habit_htmx_response(
        self, test_storage, deterministic, client
    ):
        """Create habit returns HX-Redirect header."""
        response = client.post(
            "/habits",
            data={"type": "binary", "id": "new_habit", "name": "New Habit"},
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "HX-Redirect" in response.headers
        assert response.headers["HX-Redirect"] == "/habits/new_habit/edit"

    def test_delete_habit_htmx_response(
        self, sample_habits, deterministic, snapshot_html, client
    ):
        """Archive habit returns updated habit list partial."""
        response = client.delete(
            "/habits/workout",
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200
        assert response.text == snapshot_html

    def test_update_habit_htmx_response(
        self, sample_habits, deterministic, snapshot, client
    ):
        """Update habit returns 'Saved' text."""
        response = client.put(
            "/habits/workout",
            data={"name": "Exercise Daily"},
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200
        assert response.text == snapshot

    def test_reorder_habits_htmx_response(
        self, sample_habits, deterministic, snapshot_html, client
    ):
        """Reorder habits returns updated habit list partial."""
        response = client.post(
            "/habits/reorder",
            json=["notes", "mood", "workout"],  # Reversed order
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200
        assert response.text == snapshot_html
```

### Success Criteria

#### Automated Verification:
- [ ] `make test` passes
- [ ] All new snapshot tests pass
- [ ] Snapshot files created for HTMX responses

#### Manual Verification:
- [ ] HTMX partial responses are captured as separate snapshots
- [ ] Redirects are tested but not snapshotted (behavior verification only)

---

## Phase 4: HTMX Attribute Validation Helpers

### Overview
Add justhtml-based assertion helpers to validate critical HTMX attributes are preserved.

### Changes Required

#### Create tests/htmx_helpers.py

**File**: `tests/htmx_helpers.py`

```python
"""Helper functions for validating HTMX attributes in HTML responses.

These helpers use justhtml to parse HTML and assert on critical
HTMX attributes that must be preserved for client-side behavior.
"""

from justhtml import JustHTML
from justhtml.dom import SimpleDomNode


def parse_html(html: str) -> JustHTML:
    """Parse HTML string into JustHTML document."""
    return JustHTML(html, fragment=True)


def assert_htmx_form(
    doc: JustHTML,
    selector: str,
    *,
    hx_method: str,
    hx_target: str,
    hx_swap: str = "innerHTML",
) -> None:
    """Assert a form has required HTMX attributes.

    Args:
        doc: Parsed HTML document
        selector: CSS selector for the form
        hx_method: Expected hx-post, hx-put, or hx-delete value
        hx_target: Expected hx-target value
        hx_swap: Expected hx-swap value (default: innerHTML)
    """
    results = doc.query(selector)
    assert len(results) > 0, f"Form not found: {selector}"
    form = results[0]

    # Determine which hx- attribute to check
    if "hx-post" in form.attrs:
        assert form.attrs["hx-post"] == hx_method, f"Expected hx-post={hx_method}"
    elif "hx-put" in form.attrs:
        assert form.attrs["hx-put"] == hx_method, f"Expected hx-put={hx_method}"
    elif "hx-delete" in form.attrs:
        assert form.attrs["hx-delete"] == hx_method, f"Expected hx-delete={hx_method}"
    else:
        raise AssertionError(f"No HTMX method attribute found on {selector}")

    assert form.attrs.get("hx-target") == hx_target, f"Expected hx-target={hx_target}"
    assert form.attrs.get("hx-swap") == hx_swap, f"Expected hx-swap={hx_swap}"


def assert_htmx_button(
    doc: JustHTML,
    selector: str,
    *,
    hx_method: str,
    hx_target: str | None = None,
    hx_confirm: str | None = None,
) -> None:
    """Assert a button has required HTMX attributes.

    Args:
        doc: Parsed HTML document
        selector: CSS selector for the button
        hx_method: Expected hx-delete or hx-post value
        hx_target: Expected hx-target value (optional)
        hx_confirm: Expected hx-confirm message substring (optional)
    """
    results = doc.query(selector)
    assert len(results) > 0, f"Button not found: {selector}"
    button = results[0]

    if "hx-delete" in button.attrs:
        assert button.attrs["hx-delete"] == hx_method
    elif "hx-post" in button.attrs:
        assert button.attrs["hx-post"] == hx_method
    else:
        raise AssertionError(f"No HTMX method on button: {selector}")

    if hx_target:
        assert button.attrs.get("hx-target") == hx_target

    if hx_confirm:
        assert hx_confirm in button.attrs.get("hx-confirm", "")


def assert_data_attributes(
    doc: JustHTML,
    selector: str,
    **expected_attrs: str,
) -> None:
    """Assert an element has expected data-* attributes.

    Args:
        doc: Parsed HTML document
        selector: CSS selector
        **expected_attrs: Expected data attributes (without 'data-' prefix)
            Example: habit_id="workout" checks data-habit-id="workout"
    """
    results = doc.query(selector)
    assert len(results) > 0, f"Element not found: {selector}"
    element = results[0]

    for attr, value in expected_attrs.items():
        # Convert snake_case to kebab-case for data attributes
        data_attr = f"data-{attr.replace('_', '-')}"
        assert element.attrs.get(data_attr) == value, (
            f"Expected {data_attr}={value}, got {element.attrs.get(data_attr)}"
        )


def assert_element_exists(doc: JustHTML, selector: str) -> None:
    """Assert an element exists in the HTML.

    Args:
        doc: Parsed HTML document
        selector: CSS selector
    """
    results = doc.query(selector)
    assert len(results) > 0, f"Element not found: {selector}"


def assert_element_count(doc: JustHTML, selector: str, count: int) -> None:
    """Assert a specific number of elements match the selector.

    Args:
        doc: Parsed HTML document
        selector: CSS selector
        count: Expected number of matches
    """
    elements = doc.query(selector)
    assert len(elements) == count, (
        f"Expected {count} elements matching {selector}, found {len(elements)}"
    )
```

#### Add HTMX attribute tests to test_snapshots.py

**File**: `tests/test_snapshots.py`
**Changes**: Add new test class

```python
from tests.htmx_helpers import (
    assert_data_attributes,
    assert_element_count,
    assert_element_exists,
    assert_htmx_button,
    assert_htmx_form,
    parse_html,
)


# =============================================================================
# HTMX Attribute Validation Tests
# =============================================================================


class TestHTMXAttributes:
    """Validate critical HTMX attributes are present on forms and buttons."""

    def test_index_form_attributes(self, sample_habits, deterministic, client):
        """Index page form has correct HTMX attributes for auto-save."""
        response = client.get("/?day=2025-01-15")
        doc = parse_html(response.text)

        assert_htmx_form(
            doc,
            "form",
            hx_method="save",
            hx_target="#save-status",
            hx_swap="innerHTML",
        )
        assert_element_exists(doc, "#save-status")

    def test_index_habit_data_attributes(
        self, sample_habits, deterministic, client
    ):
        """Index page habit groups have data attributes for keyboard shortcuts."""
        response = client.get("/?day=2025-01-15")
        doc = parse_html(response.text)

        # Check first habit has required data attributes
        assert_data_attributes(
            doc,
            ".habit-group",
            habit_id="workout",
            habit_type="binary",
        )

    def test_habits_page_archive_button_attributes(
        self, sample_habits, deterministic, client
    ):
        """Archive button has correct HTMX attributes and confirmation."""
        response = client.get("/habits")
        doc = parse_html(response.text)

        # Find archive button for first habit
        assert_htmx_button(
            doc,
            'button[hx-delete^="habits/"]',
            hx_method="habits/workout",
            hx_target="#habit-list",
            hx_confirm="Archive",
        )

    def test_habits_page_sortable_structure(
        self, sample_habits, deterministic, client
    ):
        """Habit list has structure required for SortableJS."""
        response = client.get("/habits")
        doc = parse_html(response.text)

        assert_element_exists(doc, "#habit-list")
        assert_element_exists(doc, "#sortable-habits")

        # Each habit item has data-id for sorting
        assert_element_count(doc, ".habit-list-item[data-id]", 3)

    def test_edit_form_attributes(self, sample_habits, deterministic, client):
        """Edit form has correct HTMX attributes for auto-save."""
        response = client.get("/habits/workout/edit")
        doc = parse_html(response.text)

        assert_htmx_form(
            doc,
            "form",
            hx_method="../workout",
            hx_target="#save-status",
            hx_swap="innerHTML",
        )
        assert_element_exists(doc, "#save-status")
```

### Success Criteria

#### Automated Verification:
- [ ] `make test` passes
- [ ] HTMX attribute tests catch intentional breakage
- [ ] `make fix` passes (no linting errors in helpers)

#### Manual Verification:
- [ ] Temporarily breaking an HTMX attribute causes test failure
- [ ] Error messages clearly identify which attribute is wrong

---

## Phase 5: Documentation and CI Integration

### Overview
Document the snapshot testing workflow and ensure CI properly handles snapshots.

### Changes Required

#### Update CLAUDE.md

**File**: `CLAUDE.md`
**Changes**: Add snapshot testing section

```markdown
## Snapshot Testing

The project uses Syrupy for HTTP response snapshots:

```bash
# Run snapshot tests
uv run pytest tests/test_snapshots.py -v

# Update snapshots after intentional changes
uv run pytest tests/test_snapshots.py --snapshot-update

# Warn about unused snapshots without failing
uv run pytest --snapshot-warn-unused
```

Snapshot files are stored in `tests/__snapshots__/` and should be committed.
Review snapshot changes in PRs as carefully as code changes.

### Determinism

Snapshot tests use fixtures for reproducibility:
- `frozen_time`: Freezes time to 2025-01-15 10:30:00
- `mock_uuid`: Generates predictable UUIDs (00000000-0000-0000-0000-000000000001, etc.)
- `deterministic`: Combines both for full determinism
```

#### Add Makefile target (if Makefile exists)

**File**: `Makefile`
**Changes**: Add snapshot-related targets

```makefile
.PHONY: snapshot-update
snapshot-update:  ## Update snapshot files
	uv run pytest tests/test_snapshots.py --snapshot-update

.PHONY: snapshot-check
snapshot-check:  ## Check for unused snapshots
	uv run pytest --snapshot-warn-unused
```

### Success Criteria

#### Automated Verification:
- [ ] `make test` includes snapshot tests in CI
- [ ] `make help` shows snapshot targets (if Makefile updated)

#### Manual Verification:
- [ ] Documentation is clear and helpful
- [ ] Snapshot update workflow is documented

---

## Testing Strategy

### New Tests to Write

| Test Category | Test Count | Purpose |
|--------------|------------|---------|
| Index page snapshots | 3 | Empty state, with habits, with entries |
| Habits page snapshots | 3 | Empty, active, archived |
| Edit page snapshots | 3 | Binary, single-select, journal |
| Calendar snapshots | 3 | Empty, with entries, with legend |
| API snapshots | 2 | Entry count endpoint |
| POST/PUT/DELETE snapshots | 5 | HTMX responses for mutations |
| HTMX attribute tests | 5 | Validate critical attributes |

**Total: ~24 new tests**

### Edge Cases

1. **Empty states**: All pages should render gracefully with no data
2. **Archived habits**: Should appear differently in lists, excluded from forms
3. **All habit types**: Each type renders different UI in edit/index pages
4. **Date navigation**: Prev/next links work correctly
5. **HTMX vs non-HTMX**: Both paths return appropriate responses

### Test Isolation

All tests use:
- `test_storage` fixture for isolated storage per test
- `frozen_time` for deterministic dates/times
- `mock_uuid` for predictable IDs
- `tmp_path` (via test_storage) for file isolation

## Code References

- `tests/conftest.py:1-18` - Existing fixtures
- `tests/test_main.py:1-50` - Example test patterns
- `src/habit_tracker/main.py:1-50` - Route definitions
- `src/habit_tracker/main.py:100-120` - HTMX detection pattern
- `src/habit_tracker/templates/index.html:13` - Form with hx-post
- `src/habit_tracker/templates/habits.html:18` - Create form
- `src/habit_tracker/templates/partials/habit_list.html:17-20` - Delete button

## Open Questions

None - all questions resolved through research:

1. **Snapshot granularity**: One snapshot per test (answered: yes, using class organization)
2. **Dynamic content handling**: Use deterministic fixtures over matchers (answered: frozen_time + mock_uuid)
3. **Test file location**: Dedicated `test_snapshots.py` file (answered: separate from test_main.py)
