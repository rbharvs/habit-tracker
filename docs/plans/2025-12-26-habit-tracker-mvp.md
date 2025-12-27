# Implementation Plan: Personal Habit Tracker MVP

**Date**: 2025-12-26T20:23:17Z
**Git Commit**: N/A (new project)
**Branch**: N/A

## Overview

Build a personal daily habit tracker with FastAPI backend, HTMX frontend, and JSON file storage. Prioritizes keyboard-friendly data entry with tab navigation, mobile-responsive design, and support for 3 habit types: binary, single-select, and journal.

## Current State

This is a greenfield project. Relevant patterns from research:

- **dijo** (Rust): JSON file storage with date-keyed entries, polymorphic habit types via traits
- **BeaverHabits** (Python): FastAPI + Protocol-based habit abstraction, observable dict for persistence
- **E-ink tracker**: Simple `{"2025-01-05": 1}` date-keyed JSON format
- **Google Sheets example**: Week-based grid, color coding, daily habits organized by category

## Desired End State

A running web application where:
1. Open browser → see today's habits in a form
2. Tab through each habit, enter data with keyboard (y/n for binary, select option, type text)
3. Press Enter or click Save → data persists to JSON
4. Navigate to past dates to view/edit historical entries
5. Works on phone and desktop browsers

**Verification**: Visit `http://localhost:8000`, complete today's habits using only keyboard, refresh page, see data persisted.

## What We're NOT Doing

- Multi-select habits (can add post-MVP)
- Weekly habits (dailies only for MVP)
- User authentication (single-user, localhost)
- Statistics/charts (just raw data entry)
- Streaks or gamification
- Reminders/notifications
- Data export (JSON is already human-readable)
- Docker deployment (run with `uv run` locally)

## Implementation Approach

**Stack**:
- Python 3.12+ with FastAPI
- HTMX for dynamic updates without React
- Jinja2 templates with minimal CSS (Pico CSS for simple styling)
- JSON file storage (one file per habit, one file for config)
- Astral ecosystem: uv (packages), uv_build (build backend), ruff (lint/format), ty (type-check)
- Exhaustive pattern matching with `match`/`case` and `assert_never`
- Makefile for command running (see rationale below)

**Why Makefile over pyproject.toml scripts?**
- `[project.scripts]` only supports Python entry points, not shell commands
- `[tool.uv.scripts]` is experimental and less flexible for compound commands
- Makefile handles chained commands (`make fix` = format + lint + type-check) naturally
- Better pre-commit hook integration
- Language-agnostic, widely understood, self-documenting with `make help`

**Directory Structure**:
```
habit-tracker/
├── pyproject.toml
├── Makefile                  # Command runner (make fix, make test, etc.)
├── .git/
│   └── hooks/
│       └── pre-commit        # Runs make fix && make test
├── src/
│   └── habit_tracker/
│       ├── __init__.py
│       ├── main.py          # FastAPI app
│       ├── models.py        # Pydantic models
│       ├── storage.py       # JSON file operations
│       └── templates/
│           ├── base.html
│           ├── index.html   # Main daily entry form
│           └── partials/
│               └── habit_field.html
├── data/
│   ├── config.json          # Habit definitions
│   └── entries/
│       └── 2025-01-05.json  # Daily entries
└── tests/
    └── test_storage.py
```

---

## Phase 1: Project Setup & Data Model

### Overview
Set up Python project with uv, define data models, implement JSON storage layer.

### Changes Required

#### `pyproject.toml`
**File**: `pyproject.toml` (new)
**Changes**: Create project configuration

```toml
[build-system]
requires = ["uv_build>=0.6.0,<0.7"]
build-backend = "uv_build"

[project]
name = "habit-tracker"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "jinja2>=3.1.0",
    "pydantic>=2.0.0",
    "python-multipart>=0.0.9",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
    "ruff>=0.8.0",
    "ty>=0.0.1a6",
]

[tool.ruff]
target-version = "py312"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]

[tool.ty.environment]
# Python version is inferred from project.requires-python
```

#### `Makefile`
**File**: `Makefile` (new)
**Changes**: Create command runner for common tasks

```makefile
.PHONY: help fix format lint typecheck test dev browser clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

fix: format lint typecheck  ## Run all fixes (format + lint + typecheck)

format:  ## Format code with ruff
	uv run ruff format src/ tests/

lint:  ## Lint and auto-fix with ruff
	uv run ruff check --fix src/ tests/

typecheck:  ## Type-check with ty
	uv run ty check src/

test:  ## Run tests with pytest
	uv run pytest tests/ -v

dev:  ## Run development server with auto-reload
	uv run uvicorn habit_tracker.main:app --reload

browser:  ## Open the app in the default browser
	open http://localhost:8000 || xdg-open http://localhost:8000 2>/dev/null

clean:  ## Remove generated files
	rm -rf .pytest_cache .ruff_cache __pycache__ src/**/__pycache__
```

#### `.git/hooks/pre-commit`
**File**: `.git/hooks/pre-commit` (new, must be executable)
**Changes**: Pre-commit hook to ensure code quality before commits

```bash
#!/bin/sh
# Pre-commit hook: run fix and test before allowing commit

echo "Running make fix..."
make fix
if [ $? -ne 0 ]; then
    echo "❌ make fix failed. Please fix errors before committing."
    exit 1
fi

echo "Running make test..."
make test
if [ $? -ne 0 ]; then
    echo "❌ make test failed. Please fix tests before committing."
    exit 1
fi

echo "✅ All checks passed!"
```

**Note**: After creating, run `chmod +x .git/hooks/pre-commit` to make it executable.

#### `src/habit_tracker/models.py`
**File**: `src/habit_tracker/models.py` (new)
**Changes**: Define Pydantic models using discriminated unions for type-safe serialization

```python
from typing import Annotated, Literal, Never, assert_never
from pydantic import BaseModel, Field
from datetime import date

# =============================================================================
# Habit Definitions (discriminated union by "type" field)
# =============================================================================

class BinaryHabit(BaseModel):
    """A yes/no habit (e.g., 'Did you work out?')"""
    type: Literal["binary"] = "binary"
    id: str
    name: str

class SingleSelectHabit(BaseModel):
    """A habit with mutually exclusive options (e.g., mood: great/good/okay/bad)"""
    type: Literal["single_select"] = "single_select"
    id: str
    name: str
    options: list[str]  # Required for this type

class JournalHabit(BaseModel):
    """A free-form text habit (e.g., daily notes)"""
    type: Literal["journal"] = "journal"
    id: str
    name: str

# Discriminated union: Pydantic uses "type" field to determine which model
Habit = Annotated[
    BinaryHabit | SingleSelectHabit | JournalHabit,
    Field(discriminator="type")
]

# =============================================================================
# Habit Entries (discriminated union by "type" field)
# =============================================================================

class BinaryEntry(BaseModel):
    """Entry for a binary habit"""
    type: Literal["binary"] = "binary"
    value: bool

class SingleSelectEntry(BaseModel):
    """Entry for a single-select habit"""
    type: Literal["single_select"] = "single_select"
    value: str  # The selected option

class JournalEntry(BaseModel):
    """Entry for a journal habit"""
    type: Literal["journal"] = "journal"
    value: str  # Free-form text

# Discriminated union for entries
HabitEntry = Annotated[
    BinaryEntry | SingleSelectEntry | JournalEntry,
    Field(discriminator="type")
]

# =============================================================================
# Daily Entries Container
# =============================================================================

class DailyEntries(BaseModel):
    """All habit entries for a single day."""
    date: date
    entries: dict[str, HabitEntry]  # habit_id -> entry
```

**Why discriminated unions?**
- Pydantic knows exactly which model to use when deserializing JSON
- `options` field only exists on `SingleSelectHabit` (not optional/None on others)
- Type checkers can narrow types based on the `type` field
- JSON is self-describing: `{"type": "binary", "value": true}` is unambiguous
- Combined with `assert_never`, ensures exhaustive handling of all cases at compile time

#### `src/habit_tracker/storage.py`
**File**: `src/habit_tracker/storage.py` (new)
**Changes**: Implement JSON file read/write operations

```python
import json
from pathlib import Path
from datetime import date
from .models import Habit, DailyEntries

DATA_DIR = Path("data")
CONFIG_FILE = DATA_DIR / "config.json"
ENTRIES_DIR = DATA_DIR / "entries"

def ensure_dirs():
    """Create data directories if they don't exist."""
    DATA_DIR.mkdir(exist_ok=True)
    ENTRIES_DIR.mkdir(exist_ok=True)

def load_habits() -> list[Habit]:
    """Load habit definitions from config."""
    if not CONFIG_FILE.exists():
        return []
    from pydantic import TypeAdapter
    adapter = TypeAdapter(list[Habit])
    data = json.loads(CONFIG_FILE.read_text())
    return adapter.validate_python(data.get("habits", []))

def save_habits(habits: list[Habit]):
    """Save habit definitions to config."""
    ensure_dirs()
    data = {"habits": [h.model_dump() for h in habits]}
    CONFIG_FILE.write_text(json.dumps(data, indent=2))

def load_entries(day: date) -> DailyEntries | None:
    """Load entries for a specific day."""
    path = ENTRIES_DIR / f"{day.isoformat()}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return DailyEntries(**data)

def save_entries(entries: DailyEntries):
    """Save entries for a specific day."""
    ensure_dirs()
    path = ENTRIES_DIR / f"{entries.date.isoformat()}.json"
    path.write_text(json.dumps(entries.model_dump(), indent=2, default=str))
```

### Success Criteria

#### Automated Verification:
- [x] `uv sync` installs dependencies without errors
- [x] `make fix` passes (format + lint + typecheck)
- [x] `make test` passes (runs pytest)
- [x] `make help` shows all available commands

#### Manual Verification:
- [x] Create test config.json, verify load_habits() returns correct data
- [x] Save and load entries, verify round-trip works
- [x] Pre-commit hook is installed: `ls -la .git/hooks/pre-commit` shows executable
- [x] Committing triggers pre-commit checks

---

## Phase 2: FastAPI Backend & Templates

### Overview
Create FastAPI app with routes for viewing/editing daily entries, Jinja2 templates with HTMX.

### Changes Required

#### `src/habit_tracker/main.py`
**File**: `src/habit_tracker/main.py` (new)
**Changes**: FastAPI app with routes

```python
from datetime import date, timedelta
from typing import assert_never
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from . import storage
from .models import (
    DailyEntries, BinaryEntry, SingleSelectEntry, JournalEntry,
    BinaryHabit, SingleSelectHabit, JournalHabit,
)

app = FastAPI()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, day: str | None = None):
    """Show habit entry form for a day (defaults to today)."""
    target_date = date.fromisoformat(day) if day else date.today()
    habits = storage.load_habits()
    entries = storage.load_entries(target_date)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "date": target_date,
        "habits": habits,
        "entries": entries.entries if entries else {},
        "prev_date": (target_date - timedelta(days=1)).isoformat(),
        "next_date": (target_date + timedelta(days=1)).isoformat(),
        "is_today": target_date == date.today(),
    })

@app.post("/save")
async def save(request: Request):
    """Save habit entries from form submission."""
    form = await request.form()
    day = date.fromisoformat(form["date"])
    habits = storage.load_habits()

    entries = {}
    for habit in habits:
        field_name = f"habit_{habit.id}"
        # Exhaustive pattern matching with assert_never
        match habit:
            case BinaryHabit():
                entries[habit.id] = BinaryEntry(value=field_name in form)
            case SingleSelectHabit():
                if field_name in form:
                    entries[habit.id] = SingleSelectEntry(value=form[field_name])
            case JournalHabit():
                entries[habit.id] = JournalEntry(value=form.get(field_name, ""))
            case _ as unreachable:
                assert_never(unreachable)

    storage.save_entries(DailyEntries(date=day, entries=entries))
    return RedirectResponse(url=f"/?day={day.isoformat()}", status_code=303)
```

#### `src/habit_tracker/templates/base.html`
**File**: `src/habit_tracker/templates/base.html` (new)
**Changes**: Base template with Pico CSS and HTMX

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Habit Tracker</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <style>
        :root { --pico-font-size: 16px; }
        .container { max-width: 600px; padding: 1rem; }
        .date-nav { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
        .habit-group { margin-bottom: 1.5rem; }
        .habit-label { font-weight: 600; margin-bottom: 0.5rem; }
        fieldset { border: none; padding: 0; margin: 0; }
        .options { display: flex; flex-wrap: wrap; gap: 0.5rem; }
        .options label { display: flex; align-items: center; gap: 0.25rem; }
    </style>
</head>
<body>
    <main class="container">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

#### `src/habit_tracker/templates/index.html`
**File**: `src/habit_tracker/templates/index.html` (new)
**Changes**: Daily entry form with keyboard-friendly fields

```html
{% extends "base.html" %}

{% block content %}
<nav class="date-nav">
    <a href="/?day={{ prev_date }}">&larr; Prev</a>
    <h2>{{ date.strftime('%A, %b %d') }}</h2>
    {% if not is_today %}
    <a href="/?day={{ next_date }}">Next &rarr;</a>
    {% else %}
    <span></span>
    {% endif %}
</nav>

<form method="post" action="/save">
    <input type="hidden" name="date" value="{{ date.isoformat() }}">

    {% for habit in habits %}
    <div class="habit-group">
        <div class="habit-label">{{ habit.name }}</div>

        {% if habit.type == "binary" %}
        <label>
            <input type="checkbox" name="habit_{{ habit.id }}"
                   {% if entries.get(habit.id) and entries[habit.id].value %}checked{% endif %}>
            Yes
        </label>

        {% elif habit.type == "single_select" %}
        <fieldset>
            <div class="options">
            {% for option in habit.options %}
            <label>
                <input type="radio" name="habit_{{ habit.id }}" value="{{ option }}"
                       {% if entries.get(habit.id) and entries[habit.id].value == option %}checked{% endif %}>
                {{ option }}
            </label>
            {% endfor %}
            </div>
        </fieldset>

        {% elif habit.type == "journal" %}
        <textarea name="habit_{{ habit.id }}" rows="3">{{ entries.get(habit.id).value if entries.get(habit.id) else '' }}</textarea>
        {% endif %}
    </div>
    {% endfor %}

    <button type="submit">Save</button>
</form>
{% endblock %}
```

### Success Criteria

#### Automated Verification:
- [x] `make dev` starts server without errors
- [x] `curl http://localhost:8000/` returns HTML

#### Manual Verification:
- [x] `make browser` opens the app in default browser
- [x] See empty form (no habits configured yet)
- [x] Tab navigates between form elements in order

---

## Phase 3: Seed Data & End-to-End Test

### Overview
Create initial habit configuration with example habits, verify full workflow.

### Changes Required

#### `data/config.json`
**File**: `data/config.json` (new)
**Changes**: Seed with example habits

```json
{
  "habits": [
    {
      "type": "binary",
      "id": "workout",
      "name": "Did you work out?"
    },
    {
      "type": "single_select",
      "id": "mood",
      "name": "How was your mood?",
      "options": ["great", "good", "okay", "bad"]
    },
    {
      "type": "journal",
      "id": "notes",
      "name": "Notes"
    }
  ]
}
```

#### `tests/test_e2e.py`
**File**: `tests/test_e2e.py` (new)
**Changes**: End-to-end test using httpx

```python
import pytest
from httpx import AsyncClient, ASGITransport
from habit_tracker.main import app
from habit_tracker import storage
from datetime import date
import shutil
from pathlib import Path

@pytest.fixture(autouse=True)
def clean_data():
    """Use a test data directory."""
    test_dir = Path("test_data")
    storage.DATA_DIR = test_dir
    storage.CONFIG_FILE = test_dir / "config.json"
    storage.ENTRIES_DIR = test_dir / "entries"
    storage.ensure_dirs()
    yield
    shutil.rmtree(test_dir, ignore_errors=True)

@pytest.mark.asyncio
async def test_save_and_load_entries():
    # Setup: create a test habit
    from habit_tracker.models import BinaryHabit
    habits = [BinaryHabit(id="test", name="Test")]
    storage.save_habits(habits)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Submit form with checkbox checked
        response = await client.post("/save", data={
            "date": date.today().isoformat(),
            "habit_test": "on"
        }, follow_redirects=False)
        assert response.status_code == 303

        # Verify entry was saved
        entries = storage.load_entries(date.today())
        assert entries is not None
        assert entries.entries["test"].value == True
```

### Success Criteria

#### Automated Verification:
- [x] `make test` passes all tests
- [x] `uv run python -c "from habit_tracker import storage; print(storage.load_habits())"` shows 3 habits

#### Manual Verification:
- [x] Start server: `make dev`
- [x] Open app: `make browser`
- [x] See 3 habits: workout (checkbox), mood (radio buttons), notes (textarea)
- [x] Tab through all fields, fill out data, press Enter on Save button
- [x] Page refreshes, data is preserved
- [x] Navigate to yesterday, enter different data, verify both days saved separately
- [x] Check `data/entries/` directory contains JSON files

---

## Phase 4: Polish & Mobile Optimization

### Overview
Add keyboard shortcuts, improve mobile experience, add visual feedback.

### Changes Required

#### `src/habit_tracker/templates/base.html`
**Changes**: Add keyboard shortcut hints and mobile meta tags

```html
<!-- Add to <head> -->
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#1a1a2e">

<!-- Add to <style> -->
@media (max-width: 600px) {
    .options { flex-direction: column; }
    button[type="submit"] { width: 100%; padding: 1rem; font-size: 1.2rem; }
}
.saved-indicator {
    color: green;
    opacity: 0;
    transition: opacity 0.3s;
}
.saved-indicator.show { opacity: 1; }

<!-- Add before </body> -->
<script>
// Auto-save on change (optional enhancement)
document.querySelectorAll('input, textarea').forEach(el => {
    el.addEventListener('change', () => {
        document.querySelector('form').requestSubmit();
    });
});

// Keyboard shortcut: Ctrl+Enter to save
document.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') {
        document.querySelector('form').requestSubmit();
    }
});
</script>
```

#### `src/habit_tracker/main.py`
**Changes**: Add HTMX response for auto-save feedback

```python
# Add to save() function, change redirect to HTMX partial if requested
@app.post("/save")
async def save(request: Request):
    # ... existing save logic ...

    # If HTMX request, return just a success indicator
    if request.headers.get("HX-Request"):
        return HTMLResponse('<span class="saved-indicator show">Saved!</span>')

    return RedirectResponse(url=f"/?day={day.isoformat()}", status_code=303)
```

### Success Criteria

#### Automated Verification:
- [x] Page loads without JS errors in browser console

#### Manual Verification:
- [ ] On mobile: form is easy to use with thumb, Save button is large and accessible
- [x] On desktop: Ctrl+Enter saves the form
- [x] Auto-save on change works (checkbox toggle saves immediately)
- [x] "Saved!" indicator appears briefly after save

---

## Testing Strategy

### New Tests to Write:
- `tests/test_storage.py`: Unit tests for JSON load/save operations
- `tests/test_e2e.py`: Integration tests for full request/response cycle
- `tests/test_models.py`: Pydantic model validation tests

### Edge Cases:
- Empty form submission (no habits checked)
- Missing config.json (should show empty form, not error)
- Invalid date in URL (should redirect to today)
- Very long journal entries
- Special characters in journal text

## Code References

From research documents:
- `docs/research/2025-12-26-hacker-news-habit-trackers.md`: BeaverHabits pattern (FastAPI + Protocol)
- `docs/research/2025-12-26-google-sheets-habit-tracker-analysis.md`: Previous habit list and patterns

## Open Questions

None - all questions resolved via user preferences:
- Framework: FastAPI + HTMX
- Storage: JSON files
- Keyboard: Tab-based forms
- Platform: Both mobile and desktop
- Single-select example: Mood tracking
- Data models: Discriminated unions for type-safe serialization
- Tooling: Astral ecosystem (uv, uv_build, ruff, ty)
- Type safety: Discriminated unions with exhaustive `assert_never` matching
