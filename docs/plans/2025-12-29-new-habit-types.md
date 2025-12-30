# Implementation Plan: Numeric, Time, and Multi-Select Habit Types

**Date**: 2025-12-29T23:43:04Z
**Git Commit**: 2000a0d732b9ab6bc8fb0e621362abd214880087
**Branch**: main

## Overview

Add three new habit types to the habit tracker:
1. **Numeric habits** - Nonnegative integer input (e.g., "glasses of water", "push-ups")
2. **Time habits** - Time-of-day input (e.g., "bedtime", "wake time")
3. **Multi-select habits** - Multiple options can be selected (e.g., "which exercises did you do?")

These types follow the established discriminated union pattern and use native HTML5 inputs for mobile-friendly UX.

Additionally, introduce Pydantic constrained types across all habit models for runtime validation:
- `HabitId` / `HabitName` - Non-empty strings
- `NonEmptyOptions` - Non-empty list for select habits
- `NonNegativeInt` - For numeric entry values

## Current State

The codebase uses Pydantic discriminated unions for type-safe habit modeling:

- **Models**: `src/habit_tracker/models.py:11-70`
  - `Habit` union: `BinaryHabit | SingleSelectHabit | JournalHabit`
  - `HabitEntry` union: `BinaryEntry | SingleSelectEntry | JournalEntry`
  - Each type has a `type: Literal["..."]` discriminator field

- **Form handling**: `src/habit_tracker/main.py:62-75`
  - Uses exhaustive `match`/`case` with `assert_never`
  - Processes form data per habit type

- **Template**: `src/habit_tracker/templates/index.html:21-43`
  - Jinja2 `{% if habit.type == "..." %}` conditionals

- **Tests**:
  - `tests/test_models.py` - Model creation and serialization
  - `tests/test_main.py` - Route testing with `TestClient`

## Desired End State

Three new habit types fully integrated:

1. **NumericHabit/NumericEntry**: Store nonnegative integers with optional unit label
2. **TimeHabit/TimeEntry**: Store `datetime.time` values
3. **MultiSelectHabit/MultiSelectEntry**: Store list of selected options

Each type:
- Has model definitions in `models.py`
- Is handled in the `/save` route in `main.py`
- Renders correctly in `index.html`
- Has unit tests for model and route behavior
- Passes `make fix` (format, lint, typecheck)

## What We're NOT Doing

- **Duration habits** - Deferred (requires unit handling complexity)
- **Counter habits** - Deferred (requires HTMX-based increment UX)
- **Rating/scale habits** - Deferred (can use numeric for now)
- **Config UI for adding habits** - Habits are still configured via JSON file
- **CSS styling for new inputs** - Use existing styles, no new CSS

## Implementation Approach

Implement all three types in a single phase since they follow the same pattern and are independent. The pattern for each type:

1. Add `*Habit` model with `type: Literal["..."]`
2. Add `*Entry` model with matching discriminator
3. Extend `Habit` and `HabitEntry` union types
4. Add `case *Habit():` in `main.py` save route
5. Add `{% elif habit.type == "..." %}` in template
6. Add unit tests for model and route

---

## Phase 1: Add New Habit Types

### Overview

Add NumericHabit, TimeHabit, and MultiSelectHabit with their corresponding entry types, form handling, and template rendering.

### Changes Required

#### 1. Models (`src/habit_tracker/models.py`)

**Add imports** (lines 1-4):
```python
from datetime import date, time
from typing import Annotated, Literal

from pydantic import BaseModel, Field, NonNegativeInt
```

**Add type aliases for constrained fields** (after imports, before BinaryHabit):
```python
# Constrained types for habit fields
HabitId = Annotated[str, Field(min_length=1)]
HabitName = Annotated[str, Field(min_length=1)]
NonEmptyOptions = Annotated[list[str], Field(min_length=1)]
```

**Update existing habits to use constrained types** (BinaryHabit, SingleSelectHabit, JournalHabit):
```python
class BinaryHabit(BaseModel):
    """A yes/no habit (e.g., 'Did you work out?')"""

    type: Literal["binary"] = "binary"
    id: HabitId
    name: HabitName


class SingleSelectHabit(BaseModel):
    """A habit with mutually exclusive options (e.g., mood: great/good/okay/bad)"""

    type: Literal["single_select"] = "single_select"
    id: HabitId
    name: HabitName
    options: NonEmptyOptions


class JournalHabit(BaseModel):
    """A free-form text habit (e.g., daily notes)"""

    type: Literal["journal"] = "journal"
    id: HabitId
    name: HabitName
```

**Add NumericHabit** (after JournalHabit, before Habit union):
```python
class NumericHabit(BaseModel):
    """A numeric habit tracking nonnegative integers (e.g., glasses of water)."""

    type: Literal["numeric"] = "numeric"
    id: HabitId
    name: HabitName
    unit: str = ""  # e.g., "glasses", "pages"
```

**Add TimeHabit** (after NumericHabit):
```python
class TimeHabit(BaseModel):
    """A time-of-day habit (e.g., bedtime, wake time)."""

    type: Literal["time"] = "time"
    id: HabitId
    name: HabitName
```

**Add MultiSelectHabit** (after TimeHabit):
```python
class MultiSelectHabit(BaseModel):
    """A habit with multiple selectable options (e.g., which exercises)."""

    type: Literal["multi_select"] = "multi_select"
    id: HabitId
    name: HabitName
    options: NonEmptyOptions
```

**Update Habit union** (line 37-39):
```python
Habit = Annotated[
    BinaryHabit | SingleSelectHabit | JournalHabit | NumericHabit | TimeHabit | MultiSelectHabit,
    Field(discriminator="type"),
]
```

**Add NumericEntry** (after JournalEntry):
```python
class NumericEntry(BaseModel):
    """Entry for a numeric habit."""

    type: Literal["numeric"] = "numeric"
    value: NonNegativeInt  # Enforced >= 0 at runtime by Pydantic
```

**Add TimeEntry** (after NumericEntry):
```python
class TimeEntry(BaseModel):
    """Entry for a time habit."""

    type: Literal["time"] = "time"
    value: time
```

**Add MultiSelectEntry** (after TimeEntry):
```python
class MultiSelectEntry(BaseModel):
    """Entry for a multi-select habit."""

    type: Literal["multi_select"] = "multi_select"
    value: list[str]  # Selected options (can be empty)
```

**Update HabitEntry union** (line 68-70):
```python
HabitEntry = Annotated[
    BinaryEntry | SingleSelectEntry | JournalEntry | NumericEntry | TimeEntry | MultiSelectEntry,
    Field(discriminator="type"),
]
```

#### 2. Route Handling (`src/habit_tracker/main.py`)

**Update imports** (lines 12-20):
```python
from .models import (
    BinaryEntry,
    BinaryHabit,
    DailyEntries,
    JournalEntry,
    JournalHabit,
    MultiSelectEntry,
    MultiSelectHabit,
    NumericEntry,
    NumericHabit,
    SingleSelectEntry,
    SingleSelectHabit,
    TimeEntry,
    TimeHabit,
)
```

**Update entries dict type annotation** (line 62):
```python
entries: dict[str, BinaryEntry | SingleSelectEntry | JournalEntry | NumericEntry | TimeEntry | MultiSelectEntry] = {}
```

**Add cases in match block** (after line 73, before `case _ as unreachable`):
```python
case NumericHabit():
    if field_name in form:
        raw = str(form[field_name]).strip()
        if raw:
            entries[habit.id] = NumericEntry(value=int(raw))
case TimeHabit():
    if field_name in form:
        raw = str(form[field_name]).strip()
        if raw:
            entries[habit.id] = TimeEntry(value=raw)
case MultiSelectHabit():
    # Multiple checkboxes with same name come as getlist
    selected = form.getlist(field_name)
    entries[habit.id] = MultiSelectEntry(value=[str(v) for v in selected])
```

#### 3. Template (`src/habit_tracker/templates/index.html`)

**Add elif blocks** (after line 42, before `{% endif %}`):
```html
{% elif habit.type == "numeric" %}
<div class="numeric-input">
    <input type="number" name="habit_{{ habit.id }}"
           value="{{ entries.get(habit.id).value if entries.get(habit.id) else '' }}"
           min="0" step="1" inputmode="numeric">
    {% if habit.unit %}<span class="unit">{{ habit.unit }}</span>{% endif %}
</div>

{% elif habit.type == "time" %}
<input type="time" name="habit_{{ habit.id }}"
       value="{{ entries.get(habit.id).value.strftime('%H:%M') if entries.get(habit.id) else '' }}">

{% elif habit.type == "multi_select" %}
<fieldset>
    <div class="options">
    {% for option in habit.options %}
    <label>
        <input type="checkbox" name="habit_{{ habit.id }}" value="{{ option }}"
               {% if entries.get(habit.id) and option in entries[habit.id].value %}checked{% endif %}>
        {{ option }}
    </label>
    {% endfor %}
    </div>
</fieldset>
```

#### 4. Model Tests (`tests/test_models.py`)

**Add imports** at top:
```python
from datetime import date, time
```

**Add NumericHabit tests**:
```python
def test_numeric_habit_creation():
    """NumericHabit can be created with required fields."""
    from habit_tracker.models import NumericHabit

    habit = NumericHabit(id="water", name="Glasses of water", unit="glasses")
    assert habit.type == "numeric"
    assert habit.id == "water"
    assert habit.name == "Glasses of water"
    assert habit.unit == "glasses"


def test_numeric_habit_unit_optional():
    """NumericHabit unit defaults to empty string."""
    from habit_tracker.models import NumericHabit

    habit = NumericHabit(id="pushups", name="Push-ups")
    assert habit.unit == ""


def test_numeric_entry_creation():
    """NumericEntry holds an integer value."""
    from habit_tracker.models import NumericEntry

    entry = NumericEntry(value=8)
    assert entry.type == "numeric"
    assert entry.value == 8


def test_numeric_entry_rejects_negative():
    """NumericEntry rejects negative values at runtime."""
    import pytest
    from pydantic import ValidationError
    from habit_tracker.models import NumericEntry

    with pytest.raises(ValidationError):
        NumericEntry(value=-1)
```

**Add constraint validation tests**:
```python
def test_habit_rejects_empty_id():
    """All habit types reject empty id."""
    import pytest
    from pydantic import ValidationError
    from habit_tracker.models import BinaryHabit

    with pytest.raises(ValidationError):
        BinaryHabit(id="", name="Test")


def test_habit_rejects_empty_name():
    """All habit types reject empty name."""
    import pytest
    from pydantic import ValidationError
    from habit_tracker.models import BinaryHabit

    with pytest.raises(ValidationError):
        BinaryHabit(id="test", name="")


def test_select_habit_rejects_empty_options():
    """SingleSelectHabit and MultiSelectHabit reject empty options list."""
    import pytest
    from pydantic import ValidationError
    from habit_tracker.models import SingleSelectHabit, MultiSelectHabit

    with pytest.raises(ValidationError):
        SingleSelectHabit(id="mood", name="Mood", options=[])

    with pytest.raises(ValidationError):
        MultiSelectHabit(id="exercises", name="Exercises", options=[])
```

**Add TimeHabit tests**:
```python
def test_time_habit_creation():
    """TimeHabit can be created with required fields."""
    from habit_tracker.models import TimeHabit

    habit = TimeHabit(id="bedtime", name="Bedtime")
    assert habit.type == "time"
    assert habit.id == "bedtime"
    assert habit.name == "Bedtime"


def test_time_entry_creation():
    """TimeEntry holds a time value."""
    from habit_tracker.models import TimeEntry

    entry = TimeEntry(value=time(22, 30))
    assert entry.type == "time"
    assert entry.value == time(22, 30)


def test_time_entry_serialization():
    """TimeEntry serializes time as ISO 8601 string."""
    from habit_tracker.models import TimeEntry

    entry = TimeEntry(value=time(22, 30))
    data = entry.model_dump(mode="json")
    assert data["value"] == "22:30:00"
```

**Add MultiSelectHabit tests**:
```python
def test_multi_select_habit_creation():
    """MultiSelectHabit can be created with options."""
    from habit_tracker.models import MultiSelectHabit

    habit = MultiSelectHabit(
        id="exercises", name="Exercises", options=["cardio", "strength", "flexibility"]
    )
    assert habit.type == "multi_select"
    assert habit.options == ["cardio", "strength", "flexibility"]


def test_multi_select_entry_creation():
    """MultiSelectEntry holds a list of selected options."""
    from habit_tracker.models import MultiSelectEntry

    entry = MultiSelectEntry(value=["cardio", "strength"])
    assert entry.type == "multi_select"
    assert entry.value == ["cardio", "strength"]


def test_multi_select_entry_empty():
    """MultiSelectEntry can have empty selection."""
    from habit_tracker.models import MultiSelectEntry

    entry = MultiSelectEntry(value=[])
    assert entry.value == []
```

**Add discriminated union tests for new types**:
```python
def test_habit_discriminated_union_with_new_types():
    """Habit union deserializes new types correctly."""
    from habit_tracker.models import Habit, NumericHabit, TimeHabit, MultiSelectHabit

    adapter = TypeAdapter(list[Habit])

    data = [
        {"type": "numeric", "id": "water", "name": "Water", "unit": "glasses"},
        {"type": "time", "id": "bedtime", "name": "Bedtime"},
        {"type": "multi_select", "id": "exercises", "name": "Exercises", "options": ["a", "b"]},
    ]

    habits = adapter.validate_python(data)
    assert len(habits) == 3
    assert isinstance(habits[0], NumericHabit)
    assert isinstance(habits[1], TimeHabit)
    assert isinstance(habits[2], MultiSelectHabit)
```

#### 5. Route Tests (`tests/test_main.py`)

**Add imports**:
```python
from datetime import date, time, timedelta

from habit_tracker.models import (
    ...
    MultiSelectHabit,
    NumericHabit,
    TimeHabit,
)
```

**Add NumericHabit route tests**:
```python
def test_save_numeric(test_storage):
    """POST /save with number creates numeric entry."""
    test_storage.save_habits([NumericHabit(id="water", name="Water", unit="glasses")])

    client = TestClient(app)
    client.post(
        "/save",
        data={"date": "2025-01-05", "habit_water": "8"},
        follow_redirects=False,
    )

    entries = test_storage.load_entries(date(2025, 1, 5))
    assert entries.entries["water"].value == 8


def test_save_numeric_empty(test_storage):
    """POST /save with empty numeric field creates no entry."""
    test_storage.save_habits([NumericHabit(id="water", name="Water")])

    client = TestClient(app)
    client.post(
        "/save",
        data={"date": "2025-01-05", "habit_water": ""},
        follow_redirects=False,
    )

    entries = test_storage.load_entries(date(2025, 1, 5))
    assert "water" not in entries.entries


def test_index_shows_numeric_habit(test_storage):
    """GET / shows numeric input with unit."""
    test_storage.save_habits([NumericHabit(id="water", name="Glasses of water", unit="glasses")])

    client = TestClient(app)
    response = client.get("/")
    assert 'type="number"' in response.text
    assert 'name="habit_water"' in response.text
    assert "glasses" in response.text
```

**Add TimeHabit route tests**:
```python
def test_save_time(test_storage):
    """POST /save with time creates time entry."""
    test_storage.save_habits([TimeHabit(id="bedtime", name="Bedtime")])

    client = TestClient(app)
    client.post(
        "/save",
        data={"date": "2025-01-05", "habit_bedtime": "22:30"},
        follow_redirects=False,
    )

    entries = test_storage.load_entries(date(2025, 1, 5))
    assert entries.entries["bedtime"].value == time(22, 30)


def test_save_time_empty(test_storage):
    """POST /save with empty time field creates no entry."""
    test_storage.save_habits([TimeHabit(id="bedtime", name="Bedtime")])

    client = TestClient(app)
    client.post(
        "/save",
        data={"date": "2025-01-05", "habit_bedtime": ""},
        follow_redirects=False,
    )

    entries = test_storage.load_entries(date(2025, 1, 5))
    assert "bedtime" not in entries.entries


def test_index_shows_time_habit(test_storage):
    """GET / shows time input."""
    test_storage.save_habits([TimeHabit(id="bedtime", name="Bedtime")])

    client = TestClient(app)
    response = client.get("/")
    assert 'type="time"' in response.text
    assert 'name="habit_bedtime"' in response.text
```

**Add MultiSelectHabit route tests**:
```python
def test_save_multi_select(test_storage):
    """POST /save with multiple checkboxes creates multi-select entry."""
    test_storage.save_habits(
        [MultiSelectHabit(id="exercises", name="Exercises", options=["cardio", "strength", "flexibility"])]
    )

    client = TestClient(app)
    client.post(
        "/save",
        data={"date": "2025-01-05", "habit_exercises": ["cardio", "strength"]},
        follow_redirects=False,
    )

    entries = test_storage.load_entries(date(2025, 1, 5))
    assert set(entries.entries["exercises"].value) == {"cardio", "strength"}


def test_save_multi_select_empty(test_storage):
    """POST /save with no checkboxes creates empty multi-select entry."""
    test_storage.save_habits(
        [MultiSelectHabit(id="exercises", name="Exercises", options=["cardio", "strength"])]
    )

    client = TestClient(app)
    client.post(
        "/save",
        data={"date": "2025-01-05"},
        follow_redirects=False,
    )

    entries = test_storage.load_entries(date(2025, 1, 5))
    assert entries.entries["exercises"].value == []


def test_index_shows_multi_select_habit(test_storage):
    """GET / shows checkboxes for multi-select options."""
    test_storage.save_habits(
        [MultiSelectHabit(id="exercises", name="Exercises", options=["cardio", "strength"])]
    )

    client = TestClient(app)
    response = client.get("/")
    assert 'type="checkbox"' in response.text
    assert 'value="cardio"' in response.text
    assert 'value="strength"' in response.text
```

### Success Criteria

#### Automated Verification:
- [x] `make fix` passes (format, lint, typecheck)
- [x] `make test` passes

#### Manual Verification:
- [x] Create a test `config.json` with one of each new habit type
- [x] Load the page and verify all three render correctly
- [x] Submit values and verify they persist after page reload
- [x] Verify mobile-friendly inputs (numeric keypad, time picker, checkboxes)

---

## Testing Strategy

### New Tests to Write:
All tests listed in Phase 1 above. Summary:
- 11 model tests (creation, serialization, constraint validation, union deserialization)
- 9 route tests (save, empty handling, template rendering)

### Edge Cases:
- Empty numeric input → no entry created
- Empty time input → no entry created
- No checkboxes selected → empty list saved
- Time input with seconds (browsers may submit "22:30:00") → Pydantic handles
- Numeric unit is optional (empty string default)
- Negative numeric value → `ValidationError` raised by Pydantic `NonNegativeInt`
- Empty habit id → `ValidationError` raised by `HabitId` constraint
- Empty habit name → `ValidationError` raised by `HabitName` constraint
- Empty options list → `ValidationError` raised by `NonEmptyOptions` constraint

## Code References

- `src/habit_tracker/models.py:11-70` - Current models with discriminated unions
- `src/habit_tracker/main.py:56-88` - Save route with match/case
- `src/habit_tracker/templates/index.html:17-44` - Habit rendering loop
- `tests/test_models.py:1-134` - Model test patterns
- `tests/test_main.py:1-250` - Route test patterns
- `docs/research/2025-12-29-habit-input-types.md` - Research document

## Open Questions

None - all questions from the research document were resolved:
1. **Validation boundaries**: Server-side enforced via Pydantic constrained types (`NonNegativeInt`, `HabitId`, `HabitName`, `NonEmptyOptions`); HTML attributes for client-side
2. **Default values**: All habits start empty (no default)
3. **Optional vs required**: Out of scope for this implementation
4. **Calendar visualization**: Out of scope (no calendar view yet)
