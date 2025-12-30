# Implementation Plan: Habit CRUD (Create, Read, Delete)

**Date**: 2025-12-30T01:22:56Z
**Git Commit**: 48d531a21c8cbe40630a012acd0cf39246cbb085
**Branch**: main

## Overview

Implement habit management functionality: create new habits, view existing habits, and delete habits (both soft-delete to archive and hard-delete with entry count warning).

## Current State

**Models** (`src/habit_tracker/models.py:16-76`):
- 6 habit types exist: `BinaryHabit`, `SingleSelectHabit`, `JournalHabit`, `NumericHabit`, `TimeHabit`, `MultiSelectHabit`
- Uses Pydantic discriminated unions with `type` field
- No archive/deleted flag currently

**Storage** (`src/habit_tracker/storage/`):
- Protocol-based with JSON and DynamoDB implementations
- Methods: `load_habits()`, `save_habits()`, `load_entries()`, `save_entries()`
- No method to count entries per habit or delete entries

**Routes** (`src/habit_tracker/main.py:41-117`):
- `GET /` - shows daily entry form
- `POST /save` - saves daily entries
- No habit CRUD routes

**Templates** (`src/habit_tracker/templates/`):
- `base.html` - layout with PicoCSS + HTMX
- `index.html` - daily entry form
- No habit management templates

## Desired End State

1. **Create habits**: Form to add new habits with type selection
2. **Read habits**: List view showing all habits with type badges
3. **Soft-delete**: Archive habit (hide from daily view but preserve entries)
4. **Hard-delete**: Permanently remove habit with warning showing entry count

**Verification**:
- All tests pass: `make test`
- Type check passes: `make fix`
- Manual testing of create/list/delete flows

## What We're NOT Doing

- **Edit/update habits** - Not requested; can be added later
- **Reordering habits** - Out of scope
- **Calendar view** - Separate feature
- **Color coding** - Separate feature
- **Keyboard shortcuts** - Separate feature

## Implementation Approach

Use progressive enhancement with HTMX for seamless UX. Keep the UI simple following existing patterns. Implement in three phases: storage layer, API routes, then templates.

For soft-delete, add an `archived` field to habits rather than a separate collection, since habits are stored as a single list.

---

## Phase 1: Storage Layer Extensions

### Overview
Add methods to count and delete entries for a habit, plus support for archived habits.

### Changes Required

#### 1.1 Add `archived` field to habit models
**File**: `src/habit_tracker/models.py`
**Changes**: Add `archived: bool = False` to all 6 habit classes

```python
class BinaryHabit(BaseModel):
    """A yes/no habit (e.g., 'Did you work out?')"""
    type: Literal["binary"] = "binary"
    id: HabitId
    name: HabitName
    archived: bool = False  # NEW
```

Apply same change to: `SingleSelectHabit`, `JournalHabit`, `NumericHabit`, `TimeHabit`, `MultiSelectHabit`

#### 1.2 Extend storage protocol
**File**: `src/habit_tracker/storage/protocol.py`
**Changes**: Add two new methods

```python
class StorageProtocol(Protocol):
    def load_habits(self) -> list[Habit]: ...
    def save_habits(self, habits: list[Habit]) -> None: ...
    def load_entries(self, day: date) -> DailyEntries | None: ...
    def save_entries(self, entries: DailyEntries) -> None: ...
    def count_entries_for_habit(self, habit_id: str) -> int: ...  # NEW
    def delete_entries_for_habit(self, habit_id: str) -> int: ...  # NEW (returns deleted count)
```

#### 1.3 Implement in JsonFileStorage
**File**: `src/habit_tracker/storage/json_storage.py`
**Changes**: Add two new methods

```python
def count_entries_for_habit(self, habit_id: str) -> int:
    """Count how many daily entry files contain an entry for this habit."""
    count = 0
    for file in self.entries_dir.glob("*.json"):
        data = json.loads(file.read_text())
        if habit_id in data.get("entries", {}):
            count += 1
    return count

def delete_entries_for_habit(self, habit_id: str) -> int:
    """Delete entries for a habit from all daily files. Returns count deleted."""
    count = 0
    for file in self.entries_dir.glob("*.json"):
        data = json.loads(file.read_text())
        if habit_id in data.get("entries", {}):
            del data["entries"][habit_id]
            file.write_text(json.dumps(data, indent=2, default=str))
            count += 1
    return count
```

#### 1.4 Implement in DynamoDBStorage
**File**: `src/habit_tracker/storage/dynamodb_storage.py`
**Changes**: Add two new methods

```python
def count_entries_for_habit(self, habit_id: str) -> int:
    """Count entries containing this habit across all dates."""
    response = self._table.query(
        KeyConditionExpression=Key("pk").eq(self._user_pk())
        & Key("sk").begins_with("ENTRY#")
    )
    count = 0
    for item in response.get("Items", []):
        if habit_id in item.get("entries", {}):
            count += 1
    return count

def delete_entries_for_habit(self, habit_id: str) -> int:
    """Delete entries for a habit from all dates. Returns count deleted."""
    response = self._table.query(
        KeyConditionExpression=Key("pk").eq(self._user_pk())
        & Key("sk").begins_with("ENTRY#")
    )
    count = 0
    for item in response.get("Items", []):
        if habit_id in item.get("entries", {}):
            entries = item.get("entries", {})
            del entries[habit_id]
            self._table.update_item(
                Key={"pk": item["pk"], "sk": item["sk"]},
                UpdateExpression="SET entries = :e",
                ExpressionAttributeValues={":e": entries},
            )
            count += 1
    return count
```

### Success Criteria

#### Automated Verification:
- [x] Tests pass: `make test`
- [x] Type check passes: `make fix`

#### Manual Verification:
- [x] Existing habits with no `archived` field still load correctly (backward compatible)

### New Tests to Write

**File**: `tests/test_storage.py` - Add:
```python
def test_count_entries_for_habit(tmp_path):
    """count_entries_for_habit counts daily files containing habit."""
    # Setup: create entries for multiple days
    # Assert: count matches expected

def test_count_entries_for_habit_empty(tmp_path):
    """count_entries_for_habit returns 0 for nonexistent habit."""

def test_delete_entries_for_habit(tmp_path):
    """delete_entries_for_habit removes habit from all daily files."""

def test_delete_entries_for_habit_returns_count(tmp_path):
    """delete_entries_for_habit returns number of files modified."""
```

---

## Phase 2: API Routes

### Overview
Add routes for listing, creating, and deleting habits.

### Changes Required

#### 2.1 Add habit list route
**File**: `src/habit_tracker/main.py`
**Changes**: Add GET route for habit management view

```python
@app.get("/habits", response_class=HTMLResponse)
def list_habits(request: Request, storage: Storage) -> HTMLResponse:
    """Show habit management page."""
    habits = storage.load_habits()
    return templates.TemplateResponse(
        request,
        "habits.html",
        {"habits": habits},
    )
```

#### 2.2 Add habit creation route
**File**: `src/habit_tracker/main.py`
**Changes**: Add POST route for creating habits

```python
@app.post("/habits", response_model=None)
def create_habit(request: Request, storage: Storage, form: FormDataDep) -> Response:
    """Create a new habit."""
    habit_type = str(form["type"])
    habit_id = str(form["id"])
    habit_name = str(form["name"])

    # Build habit based on type
    match habit_type:
        case "binary":
            new_habit = BinaryHabit(id=habit_id, name=habit_name)
        case "single_select":
            options = [str(o).strip() for o in str(form["options"]).split(",") if o.strip()]
            new_habit = SingleSelectHabit(id=habit_id, name=habit_name, options=options)
        case "journal":
            new_habit = JournalHabit(id=habit_id, name=habit_name)
        case "numeric":
            unit = str(form.get("unit", ""))
            new_habit = NumericHabit(id=habit_id, name=habit_name, unit=unit)
        case "time":
            new_habit = TimeHabit(id=habit_id, name=habit_name)
        case "multi_select":
            options = [str(o).strip() for o in str(form["options"]).split(",") if o.strip()]
            new_habit = MultiSelectHabit(id=habit_id, name=habit_name, options=options)
        case _:
            # Return error for invalid type
            return HTMLResponse("Invalid habit type", status_code=400)

    habits = storage.load_habits()
    # Check for duplicate ID
    if any(h.id == habit_id for h in habits):
        return HTMLResponse("Habit ID already exists", status_code=400)

    habits.append(new_habit)
    storage.save_habits(habits)

    if request.headers.get("HX-Request"):
        # Return updated habit list for HTMX
        return templates.TemplateResponse(request, "partials/habit_list.html", {"habits": habits})

    return RedirectResponse(url="./habits", status_code=303)
```

#### 2.3 Add habit deletion route
**File**: `src/habit_tracker/main.py`
**Changes**: Add DELETE route with soft/hard delete support

```python
@app.delete("/habits/{habit_id}", response_model=None)
def delete_habit(
    request: Request,
    storage: Storage,
    habit_id: str,
    hard: bool = False,
) -> Response:
    """Delete a habit. Use hard=true to also delete all entries."""
    habits = storage.load_habits()
    habit_idx = next((i for i, h in enumerate(habits) if h.id == habit_id), None)

    if habit_idx is None:
        return HTMLResponse("Habit not found", status_code=404)

    if hard:
        # Hard delete: remove habit and all entries
        storage.delete_entries_for_habit(habit_id)
        habits.pop(habit_idx)
    else:
        # Soft delete: mark as archived
        habit = habits[habit_idx]
        # Reconstruct with archived=True (since Pydantic models are immutable-ish)
        archived_habit = habit.model_copy(update={"archived": True})
        habits[habit_idx] = archived_habit

    storage.save_habits(habits)

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "partials/habit_list.html", {"habits": habits})

    return RedirectResponse(url="./habits", status_code=303)
```

#### 2.4 Add entry count endpoint (for delete confirmation)
**File**: `src/habit_tracker/main.py`
**Changes**: Add GET route for entry count

```python
@app.get("/habits/{habit_id}/entry-count")
def get_entry_count(storage: Storage, habit_id: str) -> dict[str, int]:
    """Get the number of entries for a habit (for delete confirmation)."""
    count = storage.count_entries_for_habit(habit_id)
    return {"count": count}
```

#### 2.5 Filter archived habits from daily view
**File**: `src/habit_tracker/main.py`
**Changes**: Update index route to exclude archived habits

```python
@app.get("/", response_class=HTMLResponse)
def index(request: Request, storage: Storage, day: str | None = None) -> HTMLResponse:
    """Show habit entry form for a day (defaults to today)."""
    target_date = date.fromisoformat(day) if day else date.today()
    habits = storage.load_habits()
    active_habits = [h for h in habits if not h.archived]  # NEW: filter archived
    entries = storage.load_entries(target_date)
    # ... rest unchanged, but use active_habits instead of habits
```

### Success Criteria

#### Automated Verification:
- [x] Tests pass: `make test`
- [x] Type check passes: `make fix`

#### Manual Verification:
- [x] `GET /habits` returns habit list page
- [x] `POST /habits` creates new habit and redirects
- [x] `DELETE /habits/{id}` archives habit
- [x] `DELETE /habits/{id}?hard=true` removes habit and entries
- [x] Archived habits don't appear on daily entry page

### New Tests to Write

**File**: `tests/test_main.py` - Add:
```python
def test_list_habits_route(test_storage):
    """GET /habits returns habit list."""

def test_create_binary_habit(test_storage):
    """POST /habits creates binary habit."""

def test_create_single_select_habit(test_storage):
    """POST /habits creates single select habit with options."""

def test_create_habit_duplicate_id_fails(test_storage):
    """POST /habits with duplicate ID returns 400."""

def test_soft_delete_habit(test_storage):
    """DELETE /habits/{id} archives habit."""

def test_hard_delete_habit(test_storage):
    """DELETE /habits/{id}?hard=true removes habit and entries."""

def test_archived_habits_hidden_from_index(test_storage):
    """GET / excludes archived habits."""

def test_entry_count_endpoint(test_storage):
    """GET /habits/{id}/entry-count returns correct count."""
```

---

## Phase 3: Templates

### Overview
Add templates for habit management UI.

### Changes Required

#### 3.1 Create habit list template
**File**: `src/habit_tracker/templates/habits.html` (NEW)

```html
{% extends "base.html" %}

{% block content %}
<nav class="date-nav">
    <a href="./">&larr; Back to Today</a>
    <h2>Manage Habits</h2>
    <span></span>
</nav>

<section id="habit-list">
    {% include "partials/habit_list.html" %}
</section>

<hr>

<h3>Add New Habit</h3>
<form method="post" action="habits" hx-post="habits" hx-target="#habit-list" hx-swap="innerHTML">
    <label>
        ID (unique, no spaces)
        <input type="text" name="id" required pattern="[a-z0-9_-]+"
               placeholder="e.g., morning_workout">
    </label>

    <label>
        Name
        <input type="text" name="name" required placeholder="e.g., Did you work out?">
    </label>

    <label>
        Type
        <select name="type" id="habit-type" onchange="toggleOptions()">
            <option value="binary">Binary (Yes/No)</option>
            <option value="single_select">Single Select</option>
            <option value="multi_select">Multi Select</option>
            <option value="numeric">Numeric</option>
            <option value="time">Time</option>
            <option value="journal">Journal</option>
        </select>
    </label>

    <div id="options-field" style="display: none;">
        <label>
            Options (comma-separated)
            <input type="text" name="options" placeholder="e.g., great, good, okay, bad">
        </label>
    </div>

    <div id="unit-field" style="display: none;">
        <label>
            Unit (optional)
            <input type="text" name="unit" placeholder="e.g., glasses, pages">
        </label>
    </div>

    <button type="submit">Create Habit</button>
</form>

<script>
function toggleOptions() {
    const type = document.getElementById('habit-type').value;
    const optionsField = document.getElementById('options-field');
    const unitField = document.getElementById('unit-field');

    optionsField.style.display = ['single_select', 'multi_select'].includes(type) ? 'block' : 'none';
    unitField.style.display = type === 'numeric' ? 'block' : 'none';
}
</script>
{% endblock %}
```

#### 3.2 Create habit list partial (for HTMX updates)
**File**: `src/habit_tracker/templates/partials/habit_list.html` (NEW)

```html
<ul class="habit-list">
{% for habit in habits %}
<li class="habit-list-item {% if habit.archived %}archived{% endif %}">
    <div class="habit-info">
        <span class="habit-type-badge">{{ habit.type | replace("_", " ") | title }}</span>
        <strong>{{ habit.name }}</strong>
        <small class="habit-id">({{ habit.id }})</small>
        {% if habit.archived %}<span class="archived-badge">Archived</span>{% endif %}
    </div>
    <div class="habit-actions">
        {% if not habit.archived %}
        <button class="outline secondary"
                hx-delete="habits/{{ habit.id }}"
                hx-target="#habit-list"
                hx-swap="innerHTML"
                hx-confirm="Archive this habit? It will be hidden from daily view but entries will be preserved.">
            Archive
        </button>
        {% endif %}
        <button class="outline secondary delete-btn"
                data-habit-id="{{ habit.id }}"
                onclick="confirmHardDelete('{{ habit.id }}', '{{ habit.name }}')">
            Delete
        </button>
    </div>
</li>
{% else %}
<li class="no-habits">No habits configured. Create one below!</li>
{% endfor %}
</ul>

<script>
async function confirmHardDelete(habitId, habitName) {
    const response = await fetch(`habits/${habitId}/entry-count`);
    const data = await response.json();
    const count = data.count;

    const message = count > 0
        ? `Permanently delete "${habitName}"? This will also delete ${count} entries. This cannot be undone!`
        : `Permanently delete "${habitName}"? This cannot be undone!`;

    if (confirm(message)) {
        htmx.ajax('DELETE', `habits/${habitId}?hard=true`, {target: '#habit-list', swap: 'innerHTML'});
    }
}
</script>
```

#### 3.3 Add styles for habit list
**File**: `src/habit_tracker/templates/base.html`
**Changes**: Add styles for habit management (in the `<style>` block)

```css
/* Habit management styles */
.habit-list {
    list-style: none;
    padding: 0;
    margin: 0;
}
.habit-list-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem;
    border: 1px solid var(--pico-muted-border-color);
    border-radius: 0.25rem;
    margin-bottom: 0.5rem;
}
.habit-list-item.archived {
    opacity: 0.6;
}
.habit-info {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
}
.habit-type-badge {
    font-size: 0.7rem;
    padding: 0.2rem 0.5rem;
    border-radius: 0.25rem;
    background: var(--pico-secondary-background);
}
.habit-id {
    color: var(--pico-muted-color);
}
.archived-badge {
    font-size: 0.7rem;
    padding: 0.2rem 0.5rem;
    border-radius: 0.25rem;
    background: #fef3c7;
    color: #92400e;
}
.habit-actions {
    display: flex;
    gap: 0.5rem;
}
.habit-actions button {
    padding: 0.25rem 0.5rem;
    font-size: 0.8rem;
    margin: 0;
}
.no-habits {
    color: var(--pico-muted-color);
    text-align: center;
    padding: 1rem;
}
```

#### 3.4 Create partials directory
**Command**: `mkdir -p src/habit_tracker/templates/partials`

### Success Criteria

#### Automated Verification:
- [x] Tests pass: `make test`
- [x] Type check passes: `make fix`

#### Manual Verification:
- [x] Navigate to `/habits` from any page
- [x] See list of habits with type badges
- [x] Create a new binary habit via form
- [x] Create a single-select habit with options
- [x] Archive a habit (soft delete)
- [x] Delete a habit permanently (see entry count warning)
- [x] Archived habits show with "Archived" badge
- [x] Archived habits don't appear on daily entry page

---

## Testing Strategy

### New Tests to Write

**`tests/test_storage.py`**:
- `test_count_entries_for_habit` - counts correctly
- `test_count_entries_for_habit_empty` - returns 0 for nonexistent
- `test_delete_entries_for_habit` - removes from all files
- `test_delete_entries_for_habit_returns_count` - returns deleted count

**`tests/test_main.py`**:
- `test_list_habits_route` - GET /habits works
- `test_create_binary_habit` - POST creates habit
- `test_create_single_select_habit` - includes options
- `test_create_habit_duplicate_id_fails` - 400 on duplicate
- `test_soft_delete_habit` - archives habit
- `test_hard_delete_habit` - removes habit and entries
- `test_archived_habits_hidden_from_index` - filtered from daily view
- `test_entry_count_endpoint` - returns correct count

### Edge Cases to Cover
- Creating habit with empty options (should fail for select types)
- Deleting nonexistent habit (404)
- Archive already-archived habit (idempotent)
- Habit ID with special characters (validation)
- Very long habit names

---

## Code References

- `src/habit_tracker/models.py:16-76` - Habit model definitions
- `src/habit_tracker/storage/protocol.py:7-13` - Storage protocol
- `src/habit_tracker/storage/json_storage.py:29-49` - JSON storage implementation
- `src/habit_tracker/storage/dynamodb_storage.py:59-112` - DynamoDB implementation
- `src/habit_tracker/main.py:41-59` - Index route pattern
- `src/habit_tracker/main.py:62-116` - Save route pattern
- `src/habit_tracker/templates/base.html:11-30` - Existing CSS styles
- `src/habit_tracker/templates/index.html:14-74` - Form patterns
- `tests/conftest.py:9-17` - Test storage fixture
- `tests/test_main.py:20-49` - Route testing patterns

## Open Questions

None - all questions resolved during research:
- Soft-delete uses `archived` field (simpler than separate collection)
- Entry count fetched via separate endpoint before hard delete confirmation
- Hard delete removes entries across all daily files
