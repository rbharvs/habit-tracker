# Implementation Plan: Calendar View & Habit Editing

**Date**: 2026-01-02T23:56:00Z
**Git Commit**: b8f2c3436bfcc565d6510165e7e8fa25b51627f4
**Branch**: main

## Overview

Add a per-habit calendar view showing entries color-coded by value, and enable simple (non-breaking) habit editing. This includes:
1. Monthly calendar grid per habit with color-coded days
2. Color configuration fields on all habit types
3. Edit form for modifying habit name, colors, and adding options

## Current State

The codebase has:

- **6 habit types** via discriminated unions (`models.py:19-85`):
  - `BinaryHabit`, `SingleSelectHabit`, `JournalHabit`, `NumericHabit`, `TimeHabit`, `MultiSelectHabit`
  - Each uses `type` field as discriminator with `Field(discriminator="type")`
  - Parallel entry types: `BinaryEntry`, `SingleSelectEntry`, etc.

- **Storage layer** (`storage/protocol.py:7-16`):
  - `StorageProtocol` with methods: `load_habits`, `save_habits`, `load_entries`, `save_entries`, `count_entries_for_habit`, `delete_entries_for_habit`
  - `JsonFileStorage` (`json_storage.py`) - file per day: `data/entries/YYYY-MM-DD.json`
  - `DynamoDBStorage` (`dynamodb_storage.py`) - single table with `sk=ENTRY#{date}`
  - **No `load_entries_range` method exists yet**

- **Routes** (`main.py`):
  - `GET /` - daily entry form
  - `POST /save` - save entries
  - `GET /habits` - habit management list
  - `POST /habits` - create habit
  - `DELETE /habits/{id}` - archive/hard delete
  - `POST /habits/{id}/move-up|move-down` - reorder
  - **No edit routes exist**

- **Templates** (`templates/`):
  - `base.html` - Pico CSS, HTMX 2.0.4, inline CSS
  - `index.html` - daily entry form with auto-save
  - `habits.html` - management page with creation form
  - `partials/habit_list.html` - reusable list component

- **Tests**:
  - Model tests in `test_models.py` with validation and roundtrip patterns
  - Storage tests in `test_storage.py` (JSON) and `test_dynamodb_storage.py` (moto)
  - Route tests in `test_main.py` with HTMX header detection
  - Pattern: `autouse` fixture overrides `get_storage` dependency

## Desired End State

1. **Calendar page** at `/calendar` and `/calendar/{habit_id}`:
   - Monthly grid showing 7 columns (Sun-Sat)
   - Days colored by entry values using habit-specific color fields
   - Navigation: prev/next month, habit selector dropdown
   - Legend for option-based habits

2. **Color fields on all habit types**:
   - `BinaryHabit`: `color_yes`, `color_no`
   - `SingleSelectHabit`/`MultiSelectHabit`: `option_colors: dict[str, str]`
   - `JournalHabit`/`TimeHabit`: `color_filled`
   - `NumericHabit`: `color_target`, `target_value` (optional)
   - All with sensible defaults, backward compatible

3. **Habit edit form** at `/habits/{habit_id}/edit`:
   - Name editable
   - Color pickers (native `<input type="color">`)
   - Options addable (append-only for select types)
   - Type and ID displayed but not editable

4. **Storage extension**:
   - `load_entries_range(start, end)` on protocol and both implementations

## What We're NOT Doing

- Deleting options from single/multi-select habits (breaks existing entries)
- Changing habit type or ID (breaks entry linkage)
- Aggregated multi-habit calendar views
- Custom color palette selector (using native color picker)
- Required target_value for numeric gradients (optional with fallback)

## Implementation Approach

Six phases, each building on the previous:

1. **Color fields on models** - Add fields with defaults, ensure backward compat
2. **Storage range query** - Add `load_entries_range` for efficient calendar data
3. **Calendar backend + UI** - Routes, templates, month navigation
4. **Calendar color rendering** - Apply colors, add legend, blend multi-select
5. **Habit edit form UI** - Edit page with color pickers
6. **Habit edit save** - PUT endpoint with validation

---

## Phase 1: Color Fields on Models + Storage Tests

### Overview
Extend all 6 habit model types with color fields. All fields have defaults for backward compatibility with existing serialized data.

### Changes Required

#### `src/habit_tracker/models.py`

**BinaryHabit** (lines 19-25):
```python
class BinaryHabit(BaseModel):
    type: Literal["binary"] = "binary"
    id: HabitId
    name: HabitName
    archived: bool = False
    color_yes: str = "#22c55e"  # green
    color_no: str = "#ef4444"   # red
```

**SingleSelectHabit** (lines 28-35):
```python
class SingleSelectHabit(BaseModel):
    type: Literal["single_select"] = "single_select"
    id: HabitId
    name: HabitName
    options: NonEmptyOptions
    archived: bool = False
    option_colors: dict[str, str] = {}  # option -> hex color, empty = use defaults
```

**JournalHabit** (lines 38-44):
```python
class JournalHabit(BaseModel):
    type: Literal["journal"] = "journal"
    id: HabitId
    name: HabitName
    archived: bool = False
    color_filled: str = "#22c55e"  # green
```

**NumericHabit** (lines 47-54):
```python
class NumericHabit(BaseModel):
    type: Literal["numeric"] = "numeric"
    id: HabitId
    name: HabitName
    unit: str = ""
    archived: bool = False
    color_target: str = "#22c55e"  # green - used for any non-zero if no target
    target_value: int | None = None  # optional, enables gradient if set
```

**TimeHabit** (lines 57-63):
```python
class TimeHabit(BaseModel):
    type: Literal["time"] = "time"
    id: HabitId
    name: HabitName
    archived: bool = False
    color_filled: str = "#22c55e"  # green
```

**MultiSelectHabit** (lines 66-73):
```python
class MultiSelectHabit(BaseModel):
    type: Literal["multi_select"] = "multi_select"
    id: HabitId
    name: HabitName
    options: NonEmptyOptions
    archived: bool = False
    option_colors: dict[str, str] = {}  # option -> hex color
```

#### `tests/test_models.py`

Add tests after existing model tests:

```python
def test_binary_habit_color_defaults():
    """BinaryHabit has default colors."""
    habit = BinaryHabit(id="test", name="Test")
    assert habit.color_yes == "#22c55e"
    assert habit.color_no == "#ef4444"

def test_binary_habit_custom_colors():
    """BinaryHabit accepts custom colors."""
    habit = BinaryHabit(id="test", name="Test", color_yes="#00ff00", color_no="#ff0000")
    assert habit.color_yes == "#00ff00"
    assert habit.color_no == "#ff0000"

def test_single_select_habit_option_colors_default_empty():
    """SingleSelectHabit option_colors defaults to empty dict."""
    habit = SingleSelectHabit(id="mood", name="Mood", options=["good", "bad"])
    assert habit.option_colors == {}

def test_single_select_habit_with_option_colors():
    """SingleSelectHabit accepts option_colors mapping."""
    habit = SingleSelectHabit(
        id="mood", name="Mood",
        options=["good", "bad"],
        option_colors={"good": "#22c55e", "bad": "#ef4444"}
    )
    assert habit.option_colors["good"] == "#22c55e"

def test_journal_habit_color_default():
    """JournalHabit has default color_filled."""
    habit = JournalHabit(id="notes", name="Notes")
    assert habit.color_filled == "#22c55e"

def test_numeric_habit_color_default():
    """NumericHabit has default color_target and None target_value."""
    habit = NumericHabit(id="water", name="Water")
    assert habit.color_target == "#22c55e"
    assert habit.target_value is None

def test_numeric_habit_with_target():
    """NumericHabit accepts target_value for gradient."""
    habit = NumericHabit(id="water", name="Water", target_value=8)
    assert habit.target_value == 8

def test_time_habit_color_default():
    """TimeHabit has default color_filled."""
    habit = TimeHabit(id="bedtime", name="Bedtime")
    assert habit.color_filled == "#22c55e"

def test_multi_select_habit_option_colors_default_empty():
    """MultiSelectHabit option_colors defaults to empty dict."""
    habit = MultiSelectHabit(id="exercises", name="Exercises", options=["cardio", "strength"])
    assert habit.option_colors == {}

def test_habit_loads_without_color_fields():
    """Habits deserialize correctly without color fields (backward compat)."""
    from pydantic import TypeAdapter

    adapter = TypeAdapter(list[Habit])
    data = [
        {"type": "binary", "id": "workout", "name": "Workout"},
        {"type": "single_select", "id": "mood", "name": "Mood", "options": ["good", "bad"]},
        {"type": "journal", "id": "notes", "name": "Notes"},
        {"type": "numeric", "id": "water", "name": "Water"},
        {"type": "time", "id": "bedtime", "name": "Bedtime"},
        {"type": "multi_select", "id": "exercises", "name": "Exercises", "options": ["a", "b"]},
    ]
    habits = adapter.validate_python(data)

    # All should have defaults
    assert habits[0].color_yes == "#22c55e"
    assert habits[1].option_colors == {}
    assert habits[2].color_filled == "#22c55e"
    assert habits[3].target_value is None
    assert habits[4].color_filled == "#22c55e"
    assert habits[5].option_colors == {}

def test_habit_color_roundtrip():
    """Habits with colors serialize and deserialize correctly."""
    original = BinaryHabit(id="test", name="Test", color_yes="#aabbcc", color_no="#ddeeff")
    data = original.model_dump()
    restored = BinaryHabit(**data)
    assert restored.color_yes == "#aabbcc"
    assert restored.color_no == "#ddeeff"
```

#### `tests/test_storage.py`

Add test for storage roundtrip with colors:

```python
def test_save_and_load_habits_with_colors(tmp_path: Path):
    """Habits with color fields roundtrip through storage."""
    storage = JsonFileStorage(data_dir=tmp_path / "data")
    habits = [
        BinaryHabit(id="workout", name="Workout", color_yes="#00ff00", color_no="#ff0000"),
        SingleSelectHabit(
            id="mood", name="Mood",
            options=["good", "bad"],
            option_colors={"good": "#22c55e"}
        ),
    ]
    storage.save_habits(habits)
    loaded = storage.load_habits()

    assert loaded[0].color_yes == "#00ff00"
    assert loaded[1].option_colors == {"good": "#22c55e"}
```

#### `tests/test_dynamodb_storage.py`

Add test for DynamoDB roundtrip with colors:

```python
def test_save_and_load_habits_with_colors(dynamodb_storage):
    """Habits with color fields roundtrip through DynamoDB."""
    habits = [
        BinaryHabit(id="workout", name="Workout", color_yes="#00ff00", color_no="#ff0000"),
        NumericHabit(id="water", name="Water", color_target="#3b82f6", target_value=8),
    ]
    dynamodb_storage.save_habits(habits)
    loaded = dynamodb_storage.load_habits()

    assert loaded[0].color_yes == "#00ff00"
    assert loaded[1].color_target == "#3b82f6"
    assert loaded[1].target_value == 8
```

### Success Criteria

#### Automated Verification:
- [x] `make test` passes (all model tests including new color tests)
- [x] `make fix` passes (formatting, linting, type checking)

#### Manual Verification:
- [x] Create habit via UI, verify it saves (new fields don't break form)
- [x] Check `data/config.json` has color fields with defaults

---

## Phase 2: Storage `load_entries_range` Method

### Overview
Add a date range query method to `StorageProtocol` and implement in both storage backends for efficient calendar data loading.

### Changes Required

#### `src/habit_tracker/storage/protocol.py`

Add method to protocol (after line 15):

```python
class StorageProtocol(Protocol):
    """Protocol defining the storage interface for habit tracking."""

    def load_habits(self) -> list[Habit]: ...
    def save_habits(self, habits: list[Habit]) -> None: ...
    def load_entries(self, day: date) -> DailyEntries | None: ...
    def save_entries(self, entries: DailyEntries) -> None: ...
    def count_entries_for_habit(self, habit_id: str) -> int: ...
    def delete_entries_for_habit(self, habit_id: str) -> int: ...
    def load_entries_range(self, start: date, end: date) -> dict[date, DailyEntries]: ...
```

#### `src/habit_tracker/storage/json_storage.py`

Add method after `delete_entries_for_habit` (after line 69):

```python
def load_entries_range(self, start: date, end: date) -> dict[date, DailyEntries]:
    """Load all entries between start and end dates (inclusive)."""
    result: dict[date, DailyEntries] = {}

    # Iterate through all entry files
    for file_path in self.entries_dir.glob("*.json"):
        # Parse date from filename (YYYY-MM-DD.json)
        try:
            file_date = date.fromisoformat(file_path.stem)
        except ValueError:
            continue  # Skip invalid filenames

        # Check if within range
        if start <= file_date <= end:
            entries = self.load_entries(file_date)
            if entries is not None:
                result[file_date] = entries

    return result
```

#### `src/habit_tracker/storage/dynamodb_storage.py`

Add method after `delete_entries_for_habit` (after line 143):

```python
def load_entries_range(self, start: date, end: date) -> dict[date, DailyEntries]:
    """Load all entries between start and end dates (inclusive)."""
    result: dict[date, DailyEntries] = {}

    # Query with sk BETWEEN for date range
    response = self._table.query(
        KeyConditionExpression=(
            Key("pk").eq(_user_pk()) &
            Key("sk").between(f"ENTRY#{start.isoformat()}", f"ENTRY#{end.isoformat()}")
        )
    )

    for item in response.get("Items", []):
        item_date = date.fromisoformat(item["date"])
        entries_data = _from_dynamodb(item["entries"])
        result[item_date] = DailyEntries(date=item_date, entries=entries_data)

    return result
```

Note: Need to import `Key` from boto3 at top of file:
```python
from boto3.dynamodb.conditions import Key
```

#### `tests/test_storage.py`

Add tests for range queries:

```python
def test_load_entries_range_returns_matching_dates(tmp_path: Path):
    """load_entries_range returns entries within date range."""
    storage = JsonFileStorage(data_dir=tmp_path / "data")

    # Create entries for 5 consecutive days
    for i in range(5):
        day = date(2025, 1, 10 + i)  # Jan 10-14
        storage.save_entries(DailyEntries(
            date=day,
            entries={"test": BinaryEntry(value=True)}
        ))

    # Query middle 3 days
    result = storage.load_entries_range(date(2025, 1, 11), date(2025, 1, 13))

    assert len(result) == 3
    assert date(2025, 1, 11) in result
    assert date(2025, 1, 12) in result
    assert date(2025, 1, 13) in result
    assert date(2025, 1, 10) not in result
    assert date(2025, 1, 14) not in result

def test_load_entries_range_empty_returns_empty_dict(tmp_path: Path):
    """load_entries_range returns empty dict when no entries in range."""
    storage = JsonFileStorage(data_dir=tmp_path / "data")

    result = storage.load_entries_range(date(2025, 1, 1), date(2025, 1, 31))

    assert result == {}

def test_load_entries_range_partial_coverage(tmp_path: Path):
    """load_entries_range works when only some dates have entries."""
    storage = JsonFileStorage(data_dir=tmp_path / "data")

    # Create entries for only 2 of 5 days in range
    storage.save_entries(DailyEntries(date=date(2025, 1, 10), entries={"a": BinaryEntry(value=True)}))
    storage.save_entries(DailyEntries(date=date(2025, 1, 14), entries={"a": BinaryEntry(value=False)}))

    result = storage.load_entries_range(date(2025, 1, 10), date(2025, 1, 14))

    assert len(result) == 2
    assert result[date(2025, 1, 10)].entries["a"].value is True
    assert result[date(2025, 1, 14)].entries["a"].value is False
```

#### `tests/test_dynamodb_storage.py`

Add tests for DynamoDB range queries:

```python
def test_load_entries_range_dynamodb(dynamodb_storage):
    """load_entries_range returns entries within date range from DynamoDB."""
    # Create entries for 5 consecutive days
    for i in range(5):
        day = date(2025, 1, 10 + i)
        dynamodb_storage.save_entries(DailyEntries(
            date=day,
            entries={"test": BinaryEntry(value=True)}
        ))

    # Query middle 3 days
    result = dynamodb_storage.load_entries_range(date(2025, 1, 11), date(2025, 1, 13))

    assert len(result) == 3
    assert date(2025, 1, 11) in result
    assert date(2025, 1, 12) in result
    assert date(2025, 1, 13) in result

def test_load_entries_range_empty_dynamodb(dynamodb_storage):
    """load_entries_range returns empty dict when no entries in DynamoDB."""
    result = dynamodb_storage.load_entries_range(date(2025, 1, 1), date(2025, 1, 31))
    assert result == {}
```

#### `tests/test_protocol.py`

Update protocol verification:

```python
def _verify_protocol(storage):
    """Helper to verify storage implements protocol methods."""
    from habit_tracker.models import BinaryEntry, BinaryHabit, DailyEntries

    # ... existing checks ...

    # Test load_entries_range
    range_result = storage.load_entries_range(date(2025, 1, 1), date(2025, 1, 31))
    assert isinstance(range_result, dict)
```

### Success Criteria

#### Automated Verification:
- [x] `make test` passes (all storage tests including new range tests)
- [x] `make fix` passes

#### Manual Verification:
- [x] None required - this is internal API

---

## Phase 3: Calendar View Backend + Basic UI

### Overview
Create calendar routes, templates, and basic navigation. Days will show but without color coding yet.

### Changes Required

#### `src/habit_tracker/main.py`

Add imports at top (around line 5):
```python
import calendar as cal
from datetime import date, time, timedelta
```

Add routes after existing routes (after line 288):

```python
@app.get("/calendar", response_class=HTMLResponse)
def calendar_redirect(request: Request, storage: Storage) -> Response:
    """Redirect to calendar for first habit."""
    habits = storage.load_habits()
    active_habits = [h for h in habits if not h.archived]
    if not active_habits:
        # No habits, show empty state
        return templates.TemplateResponse(
            request, "calendar.html",
            {"habit": None, "habits": [], "calendar_weeks": [], "year": date.today().year, "month": date.today().month}
        )
    return RedirectResponse(url=f"./calendar/{active_habits[0].id}", status_code=303)


@app.get("/calendar/{habit_id}", response_class=HTMLResponse)
def calendar_view(
    request: Request,
    storage: Storage,
    habit_id: str,
    year: int | None = None,
    month: int | None = None,
) -> HTMLResponse:
    """Calendar view for a specific habit."""
    habits = storage.load_habits()
    active_habits = [h for h in habits if not h.archived]

    # Find the requested habit
    habit = next((h for h in habits if h.id == habit_id), None)
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")

    # Default to current month
    today = date.today()
    year = year or today.year
    month = month or today.month

    # Validate month/year
    if not (1 <= month <= 12):
        month = today.month
    if not (2000 <= year <= 2100):
        year = today.year

    # Calculate calendar data
    first_day = date(year, month, 1)

    # Get days in month
    _, days_in_month = cal.monthrange(year, month)
    last_day = date(year, month, days_in_month)

    # Load entries for this month
    entries_map = storage.load_entries_range(first_day, last_day)

    # Build calendar weeks (list of lists)
    # Each week is 7 items, each item is (day_number, entry_or_none, is_current_month)
    calendar_weeks: list[list[dict]] = []

    # Start from first day of week containing first_day
    start_weekday = first_day.weekday()  # Monday=0, Sunday=6
    # Convert to Sunday=0 format
    start_weekday = (start_weekday + 1) % 7

    # Calculate start date (might be in previous month)
    week_start = first_day - timedelta(days=start_weekday)

    # Generate 6 weeks to cover all possible month layouts
    for week_num in range(6):
        week = []
        for day_offset in range(7):
            current_date = week_start + timedelta(days=week_num * 7 + day_offset)

            # Get entry for this habit on this day
            daily = entries_map.get(current_date)
            entry = daily.entries.get(habit_id) if daily else None

            week.append({
                "date": current_date,
                "day": current_date.day,
                "is_current_month": current_date.month == month,
                "is_today": current_date == today,
                "is_future": current_date > today,
                "entry": entry,
            })
        calendar_weeks.append(week)

        # Stop if we've passed the end of the month
        if week[-1]["date"] > last_day and week[-1]["date"].month != month:
            break

    # Navigation links
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1

    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1

    month_name = cal.month_name[month]

    return templates.TemplateResponse(
        request, "calendar.html", {
            "habit": habit,
            "habits": active_habits,
            "calendar_weeks": calendar_weeks,
            "year": year,
            "month": month,
            "month_name": month_name,
            "prev_year": prev_year,
            "prev_month": prev_month,
            "next_year": next_year,
            "next_month": next_month,
            "today": today,
        }
    )
```

Also add import for HTTPException if not present:
```python
from fastapi import HTTPException
```

#### `src/habit_tracker/templates/calendar.html`

Create new template:

```html
{% extends "base.html" %}

{% block content %}
<header class="date-nav">
    <a href="./habits">&larr; Manage Habits</a>
    <a href="./">&larr; Daily Entry</a>
</header>

{% if habit %}
<section class="calendar-header">
    <label>
        Habit:
        <select id="habit-selector" onchange="window.location.href='./calendar/' + this.value + '?year={{ year }}&month={{ month }}'">
            {% for h in habits %}
            <option value="{{ h.id }}" {% if h.id == habit.id %}selected{% endif %}>{{ h.name }}</option>
            {% endfor %}
        </select>
    </label>
</section>

<section class="calendar-nav">
    <a href="./calendar/{{ habit.id }}?year={{ prev_year }}&month={{ prev_month }}">&larr; {{ prev_month }}/{{ prev_year }}</a>
    <h2>{{ month_name }} {{ year }}</h2>
    <a href="./calendar/{{ habit.id }}?year={{ next_year }}&month={{ next_month }}">{{ next_month }}/{{ next_year }} &rarr;</a>
</section>

<table class="calendar-grid">
    <thead>
        <tr>
            <th>Sun</th>
            <th>Mon</th>
            <th>Tue</th>
            <th>Wed</th>
            <th>Thu</th>
            <th>Fri</th>
            <th>Sat</th>
        </tr>
    </thead>
    <tbody>
        {% for week in calendar_weeks %}
        <tr>
            {% for day in week %}
            <td class="calendar-day {% if not day.is_current_month %}other-month{% endif %} {% if day.is_today %}today{% endif %} {% if day.is_future %}future{% endif %}">
                <span class="day-number">{{ day.day }}</span>
            </td>
            {% endfor %}
        </tr>
        {% endfor %}
    </tbody>
</table>

{% else %}
<p>No habits configured. <a href="./habits">Create one first</a>.</p>
{% endif %}
{% endblock %}
```

#### `src/habit_tracker/templates/base.html`

Add calendar CSS in the `<style>` section (before closing `</style>`):

```css
/* Calendar styles */
.calendar-header {
    margin-bottom: 1rem;
}

.calendar-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
}

.calendar-nav h2 {
    margin: 0;
}

.calendar-grid {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
}

.calendar-grid th {
    padding: 0.5rem;
    text-align: center;
    font-weight: 600;
    border-bottom: 2px solid var(--pico-muted-border-color);
}

.calendar-grid td {
    padding: 0.25rem;
    text-align: center;
    vertical-align: top;
    height: 3rem;
    border: 1px solid var(--pico-muted-border-color);
}

.calendar-day {
    background: #e5e5e5;  /* default gray */
}

.calendar-day.other-month {
    opacity: 0.3;
}

.calendar-day.today {
    border: 3px solid #3b82f6 !important;
}

.calendar-day.future {
    background: transparent;
}

.day-number {
    font-size: 0.875rem;
}
```

#### Add navigation link to habits page

In `templates/habits.html`, add calendar link in header (after line 3):

```html
<header class="date-nav">
    <a href="./">&larr; Daily Entry</a>
    <a href="./calendar">Calendar View</a>
</header>
```

#### `tests/test_main.py`

Add calendar route tests:

```python
def test_calendar_redirect_to_first_habit(test_storage):
    """GET /calendar redirects to first habit's calendar."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    client = TestClient(app)
    response = client.get("/calendar", follow_redirects=False)

    assert response.status_code == 303
    assert "./calendar/workout" in response.headers["location"]

def test_calendar_redirect_skips_archived(test_storage):
    """GET /calendar skips archived habits."""
    test_storage.save_habits([
        BinaryHabit(id="archived_habit", name="Archived", archived=True),
        BinaryHabit(id="active_habit", name="Active"),
    ])

    client = TestClient(app)
    response = client.get("/calendar", follow_redirects=False)

    assert response.status_code == 303
    assert "./calendar/active_habit" in response.headers["location"]

def test_calendar_no_habits_shows_empty(test_storage):
    """GET /calendar with no habits shows empty state."""
    client = TestClient(app)
    response = client.get("/calendar")

    assert response.status_code == 200
    assert "No habits configured" in response.text

def test_calendar_habit_view(test_storage):
    """GET /calendar/{habit_id} shows calendar grid."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    client = TestClient(app)
    response = client.get("/calendar/workout")

    assert response.status_code == 200
    assert "Workout" in response.text
    assert "Sun" in response.text  # Day headers
    assert "Mon" in response.text

def test_calendar_habit_not_found(test_storage):
    """GET /calendar/{habit_id} returns 404 for unknown habit."""
    client = TestClient(app)
    response = client.get("/calendar/nonexistent")

    assert response.status_code == 404

def test_calendar_month_navigation(test_storage):
    """GET /calendar/{habit_id}?year=X&month=Y shows specified month."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    client = TestClient(app)
    response = client.get("/calendar/workout?year=2025&month=6")

    assert response.status_code == 200
    assert "June" in response.text
    assert "2025" in response.text

def test_calendar_shows_entries(test_storage):
    """Calendar shows existing entries."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])
    test_storage.save_entries(DailyEntries(
        date=date(2025, 1, 15),
        entries={"workout": BinaryEntry(value=True)}
    ))

    client = TestClient(app)
    response = client.get("/calendar/workout?year=2025&month=1")

    assert response.status_code == 200
    # Entry data is present (we'll verify colors in Phase 4)
    assert "15" in response.text
```

### Success Criteria

#### Automated Verification:
- [x] `make test` passes (all tests including new calendar tests)
- [x] `make fix` passes

#### Manual Verification:
- [x] Navigate to `/calendar` - redirects to first habit
- [x] Calendar grid displays with correct month/year
- [x] Prev/next month navigation works
- [x] Habit selector dropdown changes displayed habit
- [x] Today is highlighted with blue border
- [x] Future days have no background

---

## Phase 4: Calendar Color Rendering

### Overview
Apply colors to calendar cells based on entry values. Add legend for option-based habits.

### Changes Required

#### `src/habit_tracker/colors.py`

Create new module for color utilities:

```python
"""Color utilities for calendar rendering."""


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color (#RRGGBB) to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """Convert RGB tuple to hex color (#RRGGBB)."""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def blend_colors(colors: list[str]) -> str:
    """Blend multiple hex colors by averaging RGB values."""
    if not colors:
        return "#e5e5e5"  # default gray
    if len(colors) == 1:
        return colors[0]

    rgbs = [hex_to_rgb(c) for c in colors]
    avg_r = sum(c[0] for c in rgbs) // len(rgbs)
    avg_g = sum(c[1] for c in rgbs) // len(rgbs)
    avg_b = sum(c[2] for c in rgbs) // len(rgbs)

    return rgb_to_hex((avg_r, avg_g, avg_b))


def interpolate_color(from_color: str, to_color: str, ratio: float) -> str:
    """Interpolate between two colors based on ratio (0.0 to 1.0)."""
    ratio = max(0.0, min(1.0, ratio))  # Clamp to [0, 1]

    from_rgb = hex_to_rgb(from_color)
    to_rgb = hex_to_rgb(to_color)

    result = (
        int(from_rgb[0] + (to_rgb[0] - from_rgb[0]) * ratio),
        int(from_rgb[1] + (to_rgb[1] - from_rgb[1]) * ratio),
        int(from_rgb[2] + (to_rgb[2] - from_rgb[2]) * ratio),
    )

    return rgb_to_hex(result)


# Default gray for no entry
DEFAULT_GRAY = "#e5e5e5"

# Default color palette for options without custom colors
DEFAULT_PALETTE = [
    "#22c55e",  # green
    "#3b82f6",  # blue
    "#8b5cf6",  # purple
    "#ec4899",  # pink
    "#fbbf24",  # amber
    "#14b8a6",  # teal
    "#ef4444",  # red
    "#86efac",  # light green
    "#f97316",  # orange
]


def get_option_color(option: str, option_colors: dict[str, str], all_options: list[str]) -> str:
    """Get color for an option, using custom color or default from palette."""
    if option in option_colors:
        return option_colors[option]
    # Use palette based on option index
    if option in all_options:
        idx = all_options.index(option)
        return DEFAULT_PALETTE[idx % len(DEFAULT_PALETTE)]
    return DEFAULT_GRAY
```

#### `src/habit_tracker/main.py`

Update calendar_view to compute colors. Add import at top:
```python
from habit_tracker.colors import (
    DEFAULT_GRAY,
    blend_colors,
    get_option_color,
    interpolate_color,
)
```

Update the calendar_view function to add color calculation. Replace the week-building loop section:

```python
    # Generate 6 weeks to cover all possible month layouts
    for week_num in range(6):
        week = []
        for day_offset in range(7):
            current_date = week_start + timedelta(days=week_num * 7 + day_offset)

            # Get entry for this habit on this day
            daily = entries_map.get(current_date)
            entry = daily.entries.get(habit_id) if daily else None

            # Calculate color based on habit type and entry
            color = DEFAULT_GRAY
            if entry is not None and current_date <= today:
                color = _get_entry_color(habit, entry)

            week.append({
                "date": current_date,
                "day": current_date.day,
                "is_current_month": current_date.month == month,
                "is_today": current_date == today,
                "is_future": current_date > today,
                "entry": entry,
                "color": color,
            })
        calendar_weeks.append(week)

        # Stop if we've passed the end of the month
        if week[-1]["date"] > last_day and week[-1]["date"].month != month:
            break

    # Build legend for option-based habits
    legend = None
    match habit:
        case SingleSelectHabit() | MultiSelectHabit():
            legend = [
                {"option": opt, "color": get_option_color(opt, habit.option_colors, habit.options)}
                for opt in habit.options
            ]
        case _:
            pass
```

Add helper function after imports but before routes:

```python
def _get_entry_color(habit: Habit, entry: HabitEntry) -> str:
    """Calculate color for an entry based on habit type."""
    match habit:
        case BinaryHabit():
            if isinstance(entry, BinaryEntry):
                return habit.color_yes if entry.value else habit.color_no
        case SingleSelectHabit():
            if isinstance(entry, SingleSelectEntry):
                return get_option_color(entry.value, habit.option_colors, habit.options)
        case MultiSelectHabit():
            if isinstance(entry, MultiSelectEntry) and entry.value:
                colors = [
                    get_option_color(opt, habit.option_colors, habit.options)
                    for opt in entry.value
                ]
                return blend_colors(colors)
        case JournalHabit():
            if isinstance(entry, JournalEntry) and entry.value.strip():
                return habit.color_filled
        case NumericHabit():
            if isinstance(entry, NumericEntry) and entry.value > 0:
                if habit.target_value is not None and habit.target_value > 0:
                    ratio = min(entry.value / habit.target_value, 1.0)
                    return interpolate_color(DEFAULT_GRAY, habit.color_target, ratio)
                else:
                    # No target, just use filled color for any non-zero
                    return habit.color_target
        case TimeHabit():
            if isinstance(entry, TimeEntry):
                return habit.color_filled
        case _ as unreachable:
            assert_never(unreachable)

    return DEFAULT_GRAY
```

Update template context to include legend:

```python
    return templates.TemplateResponse(
        request, "calendar.html", {
            "habit": habit,
            "habits": active_habits,
            "calendar_weeks": calendar_weeks,
            "year": year,
            "month": month,
            "month_name": month_name,
            "prev_year": prev_year,
            "prev_month": prev_month,
            "next_year": next_year,
            "next_month": next_month,
            "today": today,
            "legend": legend,
        }
    )
```

#### `src/habit_tracker/templates/calendar.html`

Update calendar cells to use colors and add legend:

```html
<tbody>
    {% for week in calendar_weeks %}
    <tr>
        {% for day in week %}
        <td class="calendar-day {% if not day.is_current_month %}other-month{% endif %} {% if day.is_today %}today{% endif %} {% if day.is_future %}future{% endif %}"
            style="{% if not day.is_future and day.is_current_month %}background-color: {{ day.color }};{% endif %}">
            <span class="day-number">{{ day.day }}</span>
        </td>
        {% endfor %}
    </tr>
    {% endfor %}
</tbody>
```

Add legend section after the calendar table (before `{% else %}`):

```html
{% if legend %}
<section class="calendar-legend">
    <h4>Legend</h4>
    <div class="legend-items">
        {% for item in legend %}
        <div class="legend-item">
            <span class="legend-color" style="background-color: {{ item.color }};"></span>
            <span class="legend-label">{{ item.option }}</span>
        </div>
        {% endfor %}
    </div>
</section>
{% endif %}
```

#### `src/habit_tracker/templates/base.html`

Add legend CSS:

```css
/* Calendar legend */
.calendar-legend {
    margin-top: 1.5rem;
}

.calendar-legend h4 {
    margin-bottom: 0.5rem;
}

.legend-items {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.legend-color {
    width: 1rem;
    height: 1rem;
    border-radius: 3px;
    border: 1px solid var(--pico-muted-border-color);
}
```

#### `tests/test_colors.py`

Create new test file:

```python
"""Tests for color utilities."""

from habit_tracker.colors import (
    DEFAULT_GRAY,
    blend_colors,
    get_option_color,
    hex_to_rgb,
    interpolate_color,
    rgb_to_hex,
)


def test_hex_to_rgb():
    """hex_to_rgb converts hex string to RGB tuple."""
    assert hex_to_rgb("#ff0000") == (255, 0, 0)
    assert hex_to_rgb("#00ff00") == (0, 255, 0)
    assert hex_to_rgb("#0000ff") == (0, 0, 255)
    assert hex_to_rgb("#ffffff") == (255, 255, 255)
    assert hex_to_rgb("#000000") == (0, 0, 0)


def test_hex_to_rgb_without_hash():
    """hex_to_rgb works with or without # prefix."""
    assert hex_to_rgb("ff0000") == (255, 0, 0)


def test_rgb_to_hex():
    """rgb_to_hex converts RGB tuple to hex string."""
    assert rgb_to_hex((255, 0, 0)) == "#ff0000"
    assert rgb_to_hex((0, 255, 0)) == "#00ff00"
    assert rgb_to_hex((0, 0, 255)) == "#0000ff"


def test_blend_colors_empty():
    """blend_colors returns gray for empty list."""
    assert blend_colors([]) == DEFAULT_GRAY


def test_blend_colors_single():
    """blend_colors returns color unchanged for single color."""
    assert blend_colors(["#ff0000"]) == "#ff0000"


def test_blend_colors_two():
    """blend_colors averages two colors."""
    # Red + Blue = Purple (127, 0, 127)
    result = blend_colors(["#ff0000", "#0000ff"])
    assert result == "#7f007f"


def test_blend_colors_three():
    """blend_colors averages multiple colors."""
    # Red + Green + Blue = Gray (85, 85, 85)
    result = blend_colors(["#ff0000", "#00ff00", "#0000ff"])
    assert result == "#555555"


def test_interpolate_color_zero():
    """interpolate_color at 0.0 returns from_color."""
    result = interpolate_color("#000000", "#ffffff", 0.0)
    assert result == "#000000"


def test_interpolate_color_one():
    """interpolate_color at 1.0 returns to_color."""
    result = interpolate_color("#000000", "#ffffff", 1.0)
    assert result == "#ffffff"


def test_interpolate_color_half():
    """interpolate_color at 0.5 returns midpoint."""
    result = interpolate_color("#000000", "#ffffff", 0.5)
    # Midpoint of 0 and 255 is 127
    assert result == "#7f7f7f"


def test_interpolate_color_clamps():
    """interpolate_color clamps ratio to [0, 1]."""
    assert interpolate_color("#000000", "#ffffff", -0.5) == "#000000"
    assert interpolate_color("#000000", "#ffffff", 1.5) == "#ffffff"


def test_get_option_color_custom():
    """get_option_color returns custom color if defined."""
    result = get_option_color("good", {"good": "#aabbcc"}, ["good", "bad"])
    assert result == "#aabbcc"


def test_get_option_color_default_palette():
    """get_option_color uses default palette for undefined colors."""
    result = get_option_color("good", {}, ["good", "bad"])
    # First option gets first palette color
    assert result == "#22c55e"

    result = get_option_color("bad", {}, ["good", "bad"])
    # Second option gets second palette color
    assert result == "#3b82f6"


def test_get_option_color_unknown():
    """get_option_color returns gray for unknown option."""
    result = get_option_color("unknown", {}, ["good", "bad"])
    assert result == DEFAULT_GRAY
```

#### `tests/test_main.py`

Add color rendering tests:

```python
def test_calendar_binary_yes_color(test_storage):
    """Calendar shows correct color for binary yes entry."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout", color_yes="#00ff00")])
    test_storage.save_entries(DailyEntries(
        date=date(2025, 1, 15),
        entries={"workout": BinaryEntry(value=True)}
    ))

    client = TestClient(app)
    response = client.get("/calendar/workout?year=2025&month=1")

    assert "#00ff00" in response.text

def test_calendar_binary_no_color(test_storage):
    """Calendar shows correct color for binary no entry."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout", color_no="#ff0000")])
    test_storage.save_entries(DailyEntries(
        date=date(2025, 1, 15),
        entries={"workout": BinaryEntry(value=False)}
    ))

    client = TestClient(app)
    response = client.get("/calendar/workout?year=2025&month=1")

    assert "#ff0000" in response.text

def test_calendar_single_select_legend(test_storage):
    """Calendar shows legend for single-select habit."""
    test_storage.save_habits([
        SingleSelectHabit(id="mood", name="Mood", options=["good", "bad"])
    ])

    client = TestClient(app)
    response = client.get("/calendar/mood?year=2025&month=1")

    assert "Legend" in response.text
    assert "good" in response.text
    assert "bad" in response.text

def test_calendar_no_legend_for_binary(test_storage):
    """Calendar does not show legend for binary habit."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    client = TestClient(app)
    response = client.get("/calendar/workout?year=2025&month=1")

    assert "Legend" not in response.text
```

### Success Criteria

#### Automated Verification:
- [x] `make test` passes (all tests including color tests)
- [x] `make fix` passes

#### Manual Verification:
- [x] Binary habit: days show green for yes, red for no
- [x] Single-select habit: days show option colors, legend visible
- [x] Journal habit: days with text show green
- [x] Numeric habit with target: gradient from gray to green
- [x] Multi-select: blended colors for multiple selections
- [x] Future days remain transparent
- [x] Days without entries show gray

---

## Phase 5: Habit Edit Form UI

### Overview
Create edit page with form for modifying habit name, colors, and adding options.

### Changes Required

#### `src/habit_tracker/main.py`

Add edit route (after calendar routes):

```python
@app.get("/habits/{habit_id}/edit", response_class=HTMLResponse)
def edit_habit_form(request: Request, storage: Storage, habit_id: str) -> HTMLResponse:
    """Edit form for a habit."""
    habits = storage.load_habits()
    habit = next((h for h in habits if h.id == habit_id), None)

    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")

    return templates.TemplateResponse(request, "edit_habit.html", {"habit": habit})
```

#### `src/habit_tracker/templates/edit_habit.html`

Create new template:

```html
{% extends "base.html" %}

{% block content %}
<header class="date-nav">
    <a href="./habits">&larr; Back to Habits</a>
</header>

<h2>Edit Habit: {{ habit.name }}</h2>

<form method="post" action="./habits/{{ habit.id }}" hx-put="./habits/{{ habit.id }}" hx-target="body" autocomplete="off">

    <label>
        ID (cannot be changed)
        <input type="text" value="{{ habit.id }}" disabled>
    </label>

    <label>
        Type (cannot be changed)
        <input type="text" value="{{ habit.type }}" disabled>
        <small>Habit type cannot be changed after creation.</small>
    </label>

    <label>
        Name
        <input type="text" name="name" value="{{ habit.name }}" required data-1p-ignore>
    </label>

    {% if habit.type == "binary" %}
    <fieldset>
        <legend>Colors</legend>
        <div class="color-row">
            <label>
                Yes
                <input type="color" name="color_yes" value="{{ habit.color_yes }}">
            </label>
            <label>
                No
                <input type="color" name="color_no" value="{{ habit.color_no }}">
            </label>
        </div>
    </fieldset>

    {% elif habit.type == "single_select" or habit.type == "multi_select" %}
    <fieldset>
        <legend>Options & Colors</legend>
        <div id="options-list">
            {% for option in habit.options %}
            <div class="option-row">
                <input type="text" name="options" value="{{ option }}" readonly>
                <input type="color" name="option_color_{{ option }}"
                       value="{{ habit.option_colors.get(option, '#22c55e') }}">
            </div>
            {% endfor %}
        </div>
        <div class="add-option-row">
            <input type="text" id="new-option-input" placeholder="New option name" data-1p-ignore>
            <button type="button" onclick="addOption()">Add Option</button>
        </div>
        <small>Maximum 9 options. Existing options cannot be removed.</small>
    </fieldset>

    {% elif habit.type == "journal" or habit.type == "time" %}
    <fieldset>
        <legend>Color</legend>
        <label>
            Filled
            <input type="color" name="color_filled" value="{{ habit.color_filled }}">
        </label>
    </fieldset>

    {% elif habit.type == "numeric" %}
    <fieldset>
        <legend>Settings</legend>
        <label>
            Unit
            <input type="text" name="unit" value="{{ habit.unit }}" placeholder="e.g., glasses" data-1p-ignore>
        </label>
        <label>
            Target value (for gradient coloring)
            <input type="number" name="target_value" value="{{ habit.target_value or '' }}" min="1" placeholder="Optional">
        </label>
        <label>
            Target color
            <input type="color" name="color_target" value="{{ habit.color_target }}">
        </label>
    </fieldset>
    {% endif %}

    <div class="form-actions">
        <button type="submit">Save Changes</button>
        <a href="./habits" role="button" class="outline secondary">Cancel</a>
    </div>
</form>

{% block scripts %}
<script>
function addOption() {
    const input = document.getElementById('new-option-input');
    const value = input.value.trim();
    if (!value) return;

    const list = document.getElementById('options-list');
    const count = list.querySelectorAll('.option-row').length;

    if (count >= 9) {
        alert('Maximum 9 options allowed.');
        return;
    }

    const row = document.createElement('div');
    row.className = 'option-row';
    row.innerHTML = `
        <input type="text" name="options" value="${value}" readonly>
        <input type="color" name="option_color_${value}" value="#22c55e">
    `;
    list.appendChild(row);
    input.value = '';
}
</script>
{% endblock %}
{% endblock %}
```

#### `src/habit_tracker/templates/base.html`

Add edit form CSS:

```css
/* Edit form styles */
.color-row {
    display: flex;
    gap: 2rem;
}

.color-row label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.option-row {
    display: flex;
    gap: 1rem;
    margin-bottom: 0.5rem;
    align-items: center;
}

.option-row input[type="text"] {
    flex: 1;
    margin-bottom: 0;
}

.option-row input[type="color"] {
    width: 3rem;
    height: 2.5rem;
    padding: 0.25rem;
    margin-bottom: 0;
}

.add-option-row {
    display: flex;
    gap: 1rem;
    margin-top: 1rem;
}

.add-option-row input {
    flex: 1;
    margin-bottom: 0;
}

.add-option-row button {
    margin-bottom: 0;
}

.form-actions {
    display: flex;
    gap: 1rem;
    margin-top: 1.5rem;
}

input[type="color"] {
    cursor: pointer;
}
```

#### `src/habit_tracker/templates/partials/habit_list.html`

Add edit button to habit actions (after move buttons, before archive):

```html
<a href="./habits/{{ habit.id }}/edit" role="button" class="outline secondary" title="Edit">
    Edit
</a>
```

#### `tests/test_main.py`

Add edit form tests:

```python
def test_edit_habit_form_binary(test_storage):
    """GET /habits/{id}/edit shows edit form for binary habit."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    client = TestClient(app)
    response = client.get("/habits/workout/edit")

    assert response.status_code == 200
    assert "Workout" in response.text
    assert 'name="name"' in response.text
    assert 'name="color_yes"' in response.text
    assert 'name="color_no"' in response.text

def test_edit_habit_form_single_select(test_storage):
    """GET /habits/{id}/edit shows options for single-select habit."""
    test_storage.save_habits([
        SingleSelectHabit(id="mood", name="Mood", options=["good", "bad"])
    ])

    client = TestClient(app)
    response = client.get("/habits/mood/edit")

    assert response.status_code == 200
    assert "good" in response.text
    assert "bad" in response.text
    assert "Add Option" in response.text

def test_edit_habit_form_numeric(test_storage):
    """GET /habits/{id}/edit shows unit and target for numeric habit."""
    test_storage.save_habits([
        NumericHabit(id="water", name="Water", unit="glasses", target_value=8)
    ])

    client = TestClient(app)
    response = client.get("/habits/water/edit")

    assert response.status_code == 200
    assert "glasses" in response.text
    assert 'name="target_value"' in response.text
    assert 'name="unit"' in response.text

def test_edit_habit_not_found(test_storage):
    """GET /habits/{id}/edit returns 404 for unknown habit."""
    client = TestClient(app)
    response = client.get("/habits/nonexistent/edit")

    assert response.status_code == 404
```

### Success Criteria

#### Automated Verification:
- [ ] `make test` passes
- [ ] `make fix` passes

#### Manual Verification:
- [ ] Edit button appears in habit list
- [ ] Edit form loads with current values
- [ ] Binary habit shows two color pickers
- [ ] Single/multi-select shows options with color pickers
- [ ] "Add Option" button adds new option row
- [ ] Numeric shows unit and target fields
- [ ] Cancel returns to habit list

---

## Phase 6: Habit Edit Save Endpoint

### Overview
Implement PUT endpoint to save habit edits with validation.

### Changes Required

#### `src/habit_tracker/main.py`

Add PUT route:

```python
@app.put("/habits/{habit_id}", response_model=None)
def update_habit(
    request: Request,
    storage: Storage,
    habit_id: str,
    form: FormDataDep
) -> Response:
    """Update a habit's editable fields."""
    habits = storage.load_habits()
    habit_idx = next((i for i, h in enumerate(habits) if h.id == habit_id), None)

    if habit_idx is None:
        raise HTTPException(status_code=404, detail="Habit not found")

    habit = habits[habit_idx]

    # Validate name
    name = str(form.get("name", "")).strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    # Build update dict based on habit type
    updates: dict = {"name": name}

    match habit:
        case BinaryHabit():
            color_yes = str(form.get("color_yes", habit.color_yes))
            color_no = str(form.get("color_no", habit.color_no))
            if not _is_valid_hex_color(color_yes) or not _is_valid_hex_color(color_no):
                raise HTTPException(status_code=400, detail="Invalid color format")
            updates["color_yes"] = color_yes
            updates["color_no"] = color_no

        case SingleSelectHabit() | MultiSelectHabit():
            # Get options from form (includes existing + new)
            new_options = [str(o).strip() for o in form.getlist("options") if str(o).strip()]

            # Validate: all existing options must be present (no deletion)
            for existing_opt in habit.options:
                if existing_opt not in new_options:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot remove existing option: {existing_opt}"
                    )

            # Validate: max 9 options
            if len(new_options) > 9:
                raise HTTPException(status_code=400, detail="Maximum 9 options allowed")

            # Validate: unique options
            if len(new_options) != len(set(new_options)):
                raise HTTPException(status_code=400, detail="Options must be unique")

            updates["options"] = new_options

            # Build option_colors from form
            option_colors = {}
            for opt in new_options:
                color_key = f"option_color_{opt}"
                if color_key in form:
                    color = str(form[color_key])
                    if _is_valid_hex_color(color):
                        option_colors[opt] = color
            updates["option_colors"] = option_colors

        case JournalHabit() | TimeHabit():
            color_filled = str(form.get("color_filled", habit.color_filled))
            if not _is_valid_hex_color(color_filled):
                raise HTTPException(status_code=400, detail="Invalid color format")
            updates["color_filled"] = color_filled

        case NumericHabit():
            unit = str(form.get("unit", "")).strip()
            updates["unit"] = unit

            target_str = str(form.get("target_value", "")).strip()
            if target_str:
                try:
                    target_value = int(target_str)
                    if target_value < 1:
                        raise HTTPException(status_code=400, detail="Target must be positive")
                    updates["target_value"] = target_value
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid target value")
            else:
                updates["target_value"] = None

            color_target = str(form.get("color_target", habit.color_target))
            if not _is_valid_hex_color(color_target):
                raise HTTPException(status_code=400, detail="Invalid color format")
            updates["color_target"] = color_target

        case _ as unreachable:
            assert_never(unreachable)

    # Apply updates
    updated_habit = habit.model_copy(update=updates)
    habits[habit_idx] = updated_habit
    storage.save_habits(habits)

    # Response based on request type
    is_htmx = request.headers.get("HX-Request")
    if is_htmx:
        # Return redirect header for HTMX
        response = Response(status_code=200)
        response.headers["HX-Redirect"] = "./habits"
        return response
    else:
        return RedirectResponse(url="./habits", status_code=303)


def _is_valid_hex_color(color: str) -> bool:
    """Validate hex color format (#RRGGBB)."""
    if not color.startswith("#") or len(color) != 7:
        return False
    try:
        int(color[1:], 16)
        return True
    except ValueError:
        return False
```

#### `tests/test_main.py`

Add save endpoint tests:

```python
def test_update_habit_name(test_storage):
    """PUT /habits/{id} updates habit name."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    client = TestClient(app)
    response = client.put(
        "/habits/workout",
        data={"name": "Morning Workout", "color_yes": "#22c55e", "color_no": "#ef4444"},
        follow_redirects=False,
    )

    assert response.status_code == 303

    habits = test_storage.load_habits()
    assert habits[0].name == "Morning Workout"

def test_update_habit_colors(test_storage):
    """PUT /habits/{id} updates habit colors."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    client = TestClient(app)
    client.put(
        "/habits/workout",
        data={"name": "Workout", "color_yes": "#00ff00", "color_no": "#ff0000"},
        follow_redirects=False,
    )

    habits = test_storage.load_habits()
    assert habits[0].color_yes == "#00ff00"
    assert habits[0].color_no == "#ff0000"

def test_update_habit_add_option(test_storage):
    """PUT /habits/{id} can add new options to select habit."""
    test_storage.save_habits([
        SingleSelectHabit(id="mood", name="Mood", options=["good", "bad"])
    ])

    client = TestClient(app)
    client.put(
        "/habits/mood",
        data={
            "name": "Mood",
            "options": ["good", "bad", "okay"],
            "option_color_good": "#22c55e",
            "option_color_bad": "#ef4444",
            "option_color_okay": "#fbbf24",
        },
        follow_redirects=False,
    )

    habits = test_storage.load_habits()
    assert habits[0].options == ["good", "bad", "okay"]

def test_update_habit_cannot_remove_option(test_storage):
    """PUT /habits/{id} rejects option removal."""
    test_storage.save_habits([
        SingleSelectHabit(id="mood", name="Mood", options=["good", "bad"])
    ])

    client = TestClient(app)
    response = client.put(
        "/habits/mood",
        data={"name": "Mood", "options": ["good"]},  # Missing "bad"
    )

    assert response.status_code == 400
    assert "Cannot remove" in response.text

def test_update_habit_max_9_options(test_storage):
    """PUT /habits/{id} rejects more than 9 options."""
    test_storage.save_habits([
        SingleSelectHabit(id="rating", name="Rating", options=["1"])
    ])

    client = TestClient(app)
    response = client.put(
        "/habits/rating",
        data={"name": "Rating", "options": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]},
    )

    assert response.status_code == 400
    assert "Maximum 9" in response.text

def test_update_habit_invalid_color(test_storage):
    """PUT /habits/{id} rejects invalid color format."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    client = TestClient(app)
    response = client.put(
        "/habits/workout",
        data={"name": "Workout", "color_yes": "not-a-color", "color_no": "#ef4444"},
    )

    assert response.status_code == 400

def test_update_habit_empty_name(test_storage):
    """PUT /habits/{id} rejects empty name."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    client = TestClient(app)
    response = client.put(
        "/habits/workout",
        data={"name": "", "color_yes": "#22c55e", "color_no": "#ef4444"},
    )

    assert response.status_code == 400

def test_update_habit_not_found(test_storage):
    """PUT /habits/{id} returns 404 for unknown habit."""
    client = TestClient(app)
    response = client.put("/habits/nonexistent", data={"name": "Test"})

    assert response.status_code == 404

def test_update_numeric_habit(test_storage):
    """PUT /habits/{id} updates numeric habit fields."""
    test_storage.save_habits([NumericHabit(id="water", name="Water")])

    client = TestClient(app)
    client.put(
        "/habits/water",
        data={
            "name": "Water Intake",
            "unit": "glasses",
            "target_value": "8",
            "color_target": "#3b82f6",
        },
        follow_redirects=False,
    )

    habits = test_storage.load_habits()
    assert habits[0].name == "Water Intake"
    assert habits[0].unit == "glasses"
    assert habits[0].target_value == 8
    assert habits[0].color_target == "#3b82f6"

def test_update_habit_htmx(test_storage):
    """PUT /habits/{id} with HTMX returns redirect header."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    client = TestClient(app)
    response = client.put(
        "/habits/workout",
        data={"name": "Workout", "color_yes": "#22c55e", "color_no": "#ef4444"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert response.headers.get("HX-Redirect") == "./habits"
```

#### `tests/test_dynamodb_storage.py`

Add integration test:

```python
def test_update_habit_dynamodb(dynamodb_client):
    """PUT /habits/{id} persists to DynamoDB."""
    client, storage = dynamodb_client
    storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    response = client.put(
        "/habits/workout",
        data={"name": "Morning Workout", "color_yes": "#00ff00", "color_no": "#ff0000"},
        follow_redirects=False,
    )

    assert response.status_code == 303

    habits = storage.load_habits()
    assert habits[0].name == "Morning Workout"
    assert habits[0].color_yes == "#00ff00"
```

### Success Criteria

#### Automated Verification:
- [ ] `make test` passes
- [ ] `make fix` passes

#### Manual Verification:
- [ ] Edit binary habit, change name and colors, verify in calendar
- [ ] Edit single-select habit, add new option, verify in legend
- [ ] Edit numeric habit, set target, verify gradient in calendar
- [ ] Attempt to remove option - should fail with error
- [ ] Attempt empty name - should fail with error

---

## Testing Strategy

### New Tests to Write

| File | Tests |
|------|-------|
| `test_models.py` | Color field defaults, custom colors, backward compat, roundtrip |
| `test_colors.py` | hex_to_rgb, rgb_to_hex, blend_colors, interpolate_color, get_option_color |
| `test_storage.py` | `load_entries_range` with various date ranges |
| `test_dynamodb_storage.py` | Color roundtrip, `load_entries_range`, edit integration |
| `test_main.py` | Calendar routes, color rendering, edit form, PUT validation |
| `test_protocol.py` | Update `_verify_protocol` with `load_entries_range` |

### Edge Cases

- Habit with no entries in calendar month
- Multi-select with no options selected (empty list)
- Numeric habit with 0 value (no color)
- Numeric habit with value > target (cap at 1.0)
- Option color not defined (use default palette)
- Editing habit that has existing entries
- Calendar spanning year boundary (Dec to Jan)
- Adding duplicate option name (should reject)

## Code References

- `src/habit_tracker/models.py:19-85` - Habit type definitions
- `src/habit_tracker/storage/protocol.py:7-16` - StorageProtocol
- `src/habit_tracker/storage/json_storage.py:40-49` - Entry file handling
- `src/habit_tracker/storage/dynamodb_storage.py:90-112` - DynamoDB entry ops
- `src/habit_tracker/main.py:63-117` - Save endpoint pattern
- `src/habit_tracker/main.py:178-209` - Delete/archive pattern
- `src/habit_tracker/templates/base.html:23-152` - Inline CSS approach
- `src/habit_tracker/templates/habits.html:17-75` - Form pattern
- `tests/test_dynamodb_storage.py:27-44` - moto fixture pattern
- `tests/conftest.py:9-17` - Storage override fixture
