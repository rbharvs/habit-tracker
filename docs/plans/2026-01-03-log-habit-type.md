# Implementation Plan: Log Habit Type

**Date**: 2026-01-03T03:24:58Z
**Git Commit**: 9e07056a6a239ba92f069330cdefb74e81fbc7ba
**Branch**: main

## Overview

Add a new "Log" habit type for capturing timestamped text entries throughout the day. Unlike other habit types that record a single value, Log habits store a list of entries—useful for food logs, work notes, mood check-ins, etc.

## Current State

The codebase uses Pydantic discriminated unions for type-safe polymorphism with 6 existing habit types:
- `BinaryHabit` / `BinaryEntry` (models.py:19-27, 100-105)
- `SingleSelectHabit` / `SingleSelectEntry` (models.py:30-38, 107-112)
- `JournalHabit` / `JournalEntry` (models.py:41-48, 114-119)
- `NumericHabit` / `NumericEntry` (models.py:51-60, 121-126)
- `TimeHabit` / `TimeEntry` (models.py:63-70, 128-133)
- `MultiSelectHabit` / `MultiSelectEntry` (models.py:73-81, 135-140)

Each habit type requires additions to:
1. Models (Habit and Entry types, discriminated unions)
2. `/save` endpoint match statement (main.py:126-149)
3. `POST /habits` creation (main.py:184-209)
4. `PUT /habits/{habit_id}` update (main.py:510-563)
5. `_get_entry_color()` function (main.py:45-75)
6. `index.html` daily entry rendering
7. `habits.html` type dropdown
8. `edit_habit.html` configuration form

The Log type is unique because it stores a **list of structured items** (timestamp + text) rather than a single value.

## Desired End State

Users can:
1. Create a "Log" habit from the habit management page
2. Add timestamped text entries throughout the day with auto-save
3. Edit timestamps and text of existing entries
4. Delete individual entries
5. See entry count ("3 entries today")
6. Use keyboard shortcuts (A to focus input, Enter to add)
7. View log habits in calendar with color_filled for days with entries

Data model:
```python
class LogItem(BaseModel):
    timestamp: time
    text: str  # min 1 char

class LogHabit(BaseModel):
    type: Literal["log"] = "log"
    id: HabitId
    name: HabitName
    archived: bool = False
    color_filled: str = "#22c55e"

class LogEntry(BaseModel):
    type: Literal["log"] = "log"
    value: list[LogItem]  # max 100 items
```

Form encoding uses JSON in a hidden field, serialized by JavaScript on each add/edit/delete.

## What We're NOT Doing

- Searching/filtering logs
- Exporting logs
- Entry reordering (entries stay in add order)
- Rich text formatting
- Options-based create form (Log has no options like select types)
- API endpoints for external integrations (future work)

## Implementation Approach

Follow the established pattern for adding new habit types:
1. Add models first (with tests)
2. Add backend handlers (with tests)
3. Add frontend rendering (with manual verification)

Use JSON form encoding (hidden field with serialized array) to integrate with existing auto-save pattern while supporting the dynamic list UI.

---

## Phase 1: Models

### Overview
Add LogItem, LogHabit, and LogEntry models with validation constraints.

### Changes Required

#### `src/habit_tracker/models.py`

**Add LogItem model** (after line 12, before BinaryHabit):
```python
class LogItem(BaseModel):
    """A single timestamped log entry."""

    timestamp: time
    text: str = Field(min_length=1)
```

**Add LogHabit model** (after MultiSelectHabit, before Habit union ~line 82):
```python
class LogHabit(BaseModel):
    """A log habit for timestamped text entries throughout the day."""

    type: Literal["log"] = "log"
    id: HabitId
    name: HabitName
    archived: bool = False
    color_filled: str = "#22c55e"  # green
```

**Add LogEntry model** (after MultiSelectEntry, before HabitEntry union ~line 140):
```python
class LogEntry(BaseModel):
    """Entry for a log habit."""

    type: Literal["log"] = "log"
    value: list[LogItem] = Field(default_factory=list, max_length=100)
```

**Update Habit union** (models.py:85-93):
Add `LogHabit` to the union:
```python
Habit = Annotated[
    BinaryHabit
    | SingleSelectHabit
    | JournalHabit
    | NumericHabit
    | TimeHabit
    | MultiSelectHabit
    | LogHabit,
    Field(discriminator="type"),
]
```

**Update HabitEntry union** (models.py:143-151):
Add `LogEntry` to the union:
```python
HabitEntry = Annotated[
    BinaryEntry
    | SingleSelectEntry
    | JournalEntry
    | NumericEntry
    | TimeEntry
    | MultiSelectEntry
    | LogEntry,
    Field(discriminator="type"),
]
```

### Success Criteria

#### Automated Verification:
- [x] Tests pass: `make test`
- [x] Type check passes: `make fix` (includes typecheck)
- [x] Lint passes: `make fix`

#### Manual Verification:
- [x] N/A (models only, no UI yet)

---

## Phase 2: Backend Handlers

### Overview
Add Log habit handling to all backend endpoints: save, create, update, color calculation.

### Changes Required

#### `src/habit_tracker/main.py`

**Add import** (top of file with other imports):
```python
from habit_tracker.models import LogHabit, LogEntry, LogItem
```

**Update `_get_entry_color()`** (main.py:45-75, add case before default):
```python
case LogHabit():
    if isinstance(entry, LogEntry) and entry.value:
        return habit.color_filled
```

**Update `/save` endpoint** (main.py:126-149, add case before assert_never):
```python
case LogHabit():
    raw = str(form.get(field_name, "[]"))
    try:
        items_data = json.loads(raw)
        items = [
            LogItem(
                timestamp=time.fromisoformat(item["timestamp"]),
                text=item["text"]
            )
            for item in items_data
            if item.get("text", "").strip()
        ]
        entries[habit.id] = LogEntry(value=items)
    except (json.JSONDecodeError, KeyError, ValueError):
        entries[habit.id] = LogEntry(value=[])
```

**Update `POST /habits`** (main.py:184-209, add case before default error):
```python
case "log":
    new_habit = LogHabit(id=habit_id, name=habit_name)
```

**Update `PUT /habits/{habit_id}`** (main.py:510-563, add case before assert_never):
```python
case LogHabit():
    color_filled = str(form.get("color_filled", habit.color_filled))
    if not _is_valid_hex_color(color_filled):
        return PlainTextResponse(
            "Invalid color format", status_code=400
        )
    updates["color_filled"] = color_filled
```

### Success Criteria

#### Automated Verification:
- [x] Tests pass: `make test`
- [x] Type check passes: `make fix`
- [x] Lint passes: `make fix`

#### Manual Verification:
- [x] N/A (endpoints work but no UI to test them yet)

---

## Phase 3: Tests for Models and Handlers

### Overview
Add comprehensive tests for Log habit type following existing patterns.

### Changes Required

#### `tests/test_models.py`

**Add LogHabit creation test** (follow pattern from line 183-190):
```python
def test_log_habit_creation():
    habit = LogHabit(id="notes", name="Daily Notes")
    assert habit.type == "log"
    assert habit.id == "notes"
    assert habit.name == "Daily Notes"
    assert habit.archived is False
    assert habit.color_filled == "#22c55e"
```

**Add LogEntry creation test**:
```python
def test_log_entry_creation():
    entry = LogEntry(value=[
        LogItem(timestamp=time(9, 15), text="Morning standup"),
        LogItem(timestamp=time(14, 30), text="Afternoon review"),
    ])
    assert entry.type == "log"
    assert len(entry.value) == 2
    assert entry.value[0].timestamp == time(9, 15)
    assert entry.value[0].text == "Morning standup"
```

**Add LogItem validation test**:
```python
def test_log_item_requires_text():
    with pytest.raises(ValidationError):
        LogItem(timestamp=time(9, 0), text="")
```

**Add LogEntry max items test**:
```python
def test_log_entry_max_100_items():
    items = [LogItem(timestamp=time(9, 0), text=f"Item {i}") for i in range(101)]
    with pytest.raises(ValidationError):
        LogEntry(value=items)
```

**Add to discriminated union test** (update test at line 294-315):
Add log habit/entry to the test data.

#### `tests/test_main.py`

**Add save log entry test** (follow pattern from line 354-374):
```python
def test_save_log_entry(test_storage):
    test_storage.save_habits([LogHabit(id="notes", name="Notes")])
    client = TestClient(app)

    log_data = json.dumps([
        {"timestamp": "09:15", "text": "First note"},
        {"timestamp": "14:30", "text": "Second note"},
    ])
    response = client.post("/save", data={
        "date": "2025-01-05",
        "habit_notes": log_data,
    })

    assert response.status_code == 303
    entries = test_storage.load_entries(date(2025, 1, 5))
    assert entries is not None
    assert "notes" in entries.entries
    log_entry = entries.entries["notes"]
    assert isinstance(log_entry, LogEntry)
    assert len(log_entry.value) == 2
```

**Add create log habit test** (follow pattern from line 491-507):
```python
def test_create_log_habit(test_storage):
    client = TestClient(app)
    response = client.post("/habits", data={
        "type": "log",
        "id": "notes",
        "name": "Daily Notes",
    })

    assert response.status_code == 303
    habits = test_storage.load_habits()
    assert len(habits) == 1
    assert isinstance(habits[0], LogHabit)
```

**Add update log habit test** (follow pattern from line 1206-1219):
```python
def test_update_log_habit(test_storage):
    test_storage.save_habits([LogHabit(id="notes", name="Notes")])
    client = TestClient(app)

    response = client.put("/habits/notes", data={
        "name": "Work Notes",
        "color_filled": "#3b82f6",
    })

    assert response.status_code == 303
    habits = test_storage.load_habits()
    assert habits[0].name == "Work Notes"
    assert habits[0].color_filled == "#3b82f6"
```

### Success Criteria

#### Automated Verification:
- [x] Tests pass: `make test`
- [x] New tests specifically pass: `uv run pytest tests/test_models.py -k log -v`
- [x] New tests specifically pass: `uv run pytest tests/test_main.py -k log -v`

#### Manual Verification:
- [x] N/A (tests only)

---

## Phase 4: Frontend - Habit Creation Form

### Overview
Add "Log" option to the habit type dropdown in the creation form.

### Changes Required

#### `src/habit_tracker/templates/habits.html`

**Update type dropdown** (line 32-39, add new option):
```html
<select name="type" id="habit-type" onchange="toggleUnitField()">
    <option value="binary">Binary (Yes/No)</option>
    <option value="single_select">Single Select</option>
    <option value="multi_select">Multi Select</option>
    <option value="numeric">Numeric</option>
    <option value="time">Time</option>
    <option value="journal">Journal</option>
    <option value="log">Log</option>
</select>
```

### Success Criteria

#### Automated Verification:
- [x] Tests pass: `make test`
- [x] Lint passes: `make fix`

#### Manual Verification:
- [ ] Run `make dev`, go to /habits
- [ ] "Log" appears in type dropdown
- [ ] Can create a Log habit successfully
- [ ] Redirects to edit page after creation

---

## Phase 5: Frontend - Habit Edit Form

### Overview
Add Log habit configuration (color_filled) to the edit form.

### Changes Required

#### `src/habit_tracker/templates/edit_habit.html`

**Add Log habit section** (after line 69, where journal/time section ends):
```html
{% elif habit.type == "log" %}
<fieldset>
    <legend>Color</legend>
    <label>
        Filled
        <input type="color" name="color_filled" value="{{ habit.color_filled }}">
    </label>
</fieldset>
{% endif %}
```

Note: The existing `{% elif habit.type == "journal" or habit.type == "time" %}` block handles both journal and time. We need to add log to this condition OR add a separate block. Since log has the same field (color_filled), update line 62 to:
```html
{% elif habit.type == "journal" or habit.type == "time" or habit.type == "log" %}
```

### Success Criteria

#### Automated Verification:
- [x] Tests pass: `make test`
- [x] Lint passes: `make fix`

#### Manual Verification:
- [ ] Run `make dev`, create a Log habit, go to edit page
- [ ] Color picker for "Filled" appears
- [ ] Changing color auto-saves (check network tab)
- [ ] Color persists after page reload

---

## Phase 6: Frontend - Daily Entry Form

### Overview
Add Log habit rendering to index.html with full JavaScript functionality for add/edit/delete.

### Changes Required

#### `src/habit_tracker/templates/index.html`

**Add Log habit template section** (after multi_select section, before closing `</div>` of habit-group):

```html
{% elif habit.type == "log" %}
<div class="habit-header">
    <span class="habit-label">{{ habit.name }}</span>
    <span class="keyboard-hint">Press A to add</span>
</div>
<!-- Hidden field holds JSON array of log items -->
<input type="hidden" name="habit_{{ habit.id }}" id="habit_{{ habit.id }}_data"
       value="{{ entries.get(habit.id).value | tojson if entries.get(habit.id) else '[]' }}">

<div class="log-entries" id="log_{{ habit.id }}_entries">
    {% if entries.get(habit.id) and entries[habit.id].value %}
        {% for item in entries[habit.id].value %}
        <div class="log-entry">
            <input type="time" class="log-time" value="{{ item.timestamp.strftime('%H:%M') }}">
            <textarea class="log-text" rows="1">{{ item.text }}</textarea>
            <button type="button" class="log-delete" title="Delete">&times;</button>
        </div>
        {% endfor %}
    {% else %}
        <div class="empty-state">No entries yet</div>
    {% endif %}
</div>
<div class="add-log-row">
    <input type="text" class="log-input" placeholder="Add a log entry...">
    <button type="button" class="log-add-btn">Add</button>
</div>
<div class="log-count" id="log_{{ habit.id }}_count">
    {% if entries.get(habit.id) and entries[habit.id].value %}
        {{ entries[habit.id].value | length }} entr{{ 'y' if entries[habit.id].value | length == 1 else 'ies' }} today
    {% endif %}
</div>
```

**Add Log JavaScript functions** (in the `<script>` section, after existing keyboard handlers):

```javascript
// Auto-resize textarea to fit content
function autoResizeTextarea(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = textarea.scrollHeight + 'px';
}

// Serialize log entries to hidden field and trigger auto-save
function updateLogData(habitId) {
    const entriesDiv = document.getElementById(`log_${habitId}_entries`);
    const entries = entriesDiv.querySelectorAll('.log-entry');
    const items = Array.from(entries).map(entry => ({
        timestamp: entry.querySelector('.log-time').value,
        text: entry.querySelector('.log-text').value
    })).filter(item => item.text.trim());

    document.getElementById(`habit_${habitId}_data`).value = JSON.stringify(items);
    updateLogCount(habitId, items.length);
    document.querySelector('form').requestSubmit();
}

// Update entry count display
function updateLogCount(habitId, count) {
    const countDiv = document.getElementById(`log_${habitId}_count`);
    if (count > 0) {
        countDiv.textContent = count + ' entr' + (count === 1 ? 'y' : 'ies') + ' today';
    } else {
        countDiv.textContent = '';
    }
}

// Add new log entry
function addLogEntry(habitId) {
    const group = document.querySelector(`[data-habit-id="${habitId}"]`);
    const input = group.querySelector('.log-input');
    const text = input.value.trim();
    if (!text) return;

    const entriesDiv = document.getElementById(`log_${habitId}_entries`);

    // Remove empty state if present
    const emptyState = entriesDiv.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    // Create timestamp (current time)
    const now = new Date();
    const timestamp = now.toTimeString().slice(0, 5);  // HH:MM

    // Create new entry element
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `
        <input type="time" class="log-time" value="${timestamp}">
        <textarea class="log-text" rows="1">${text}</textarea>
        <button type="button" class="log-delete" title="Delete">&times;</button>
    `;

    // Wire up event listeners
    wireLogEntryEvents(entry, habitId);

    entriesDiv.appendChild(entry);
    autoResizeTextarea(entry.querySelector('.log-text'));

    // Clear input and keep focus for rapid entry
    input.value = '';
    input.focus();

    updateLogData(habitId);
}

// Wire up events for a log entry (time change, text change, delete)
function wireLogEntryEvents(entry, habitId) {
    const textarea = entry.querySelector('.log-text');
    entry.querySelector('.log-time').addEventListener('change', () => updateLogData(habitId));
    textarea.addEventListener('input', () => {
        autoResizeTextarea(textarea);
        updateLogData(habitId);
    });
    entry.querySelector('.log-delete').addEventListener('click', () => {
        entry.remove();
        updateLogData(habitId);
    });
}

// Initialize all log habits on page load
document.querySelectorAll('.habit-group[data-habit-type="log"]').forEach(group => {
    const habitId = group.dataset.habitId;

    // Wire up existing entries
    group.querySelectorAll('.log-entry').forEach(entry => {
        wireLogEntryEvents(entry, habitId);
        autoResizeTextarea(entry.querySelector('.log-text'));
    });

    // Add button click
    const addBtn = group.querySelector('.log-add-btn');
    if (addBtn) {
        addBtn.addEventListener('click', () => addLogEntry(habitId));
    }

    // Enter in log input adds entry
    const logInput = group.querySelector('.log-input');
    if (logInput) {
        logInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                addLogEntry(habitId);
                e.preventDefault();
            }
        });
    }
});
```

**Add Log keyboard shortcut** (in the existing keyboard handler switch, after multi_select case):
```javascript
} else if (habitType === 'log') {
    if (key === 'a' || key === 'Enter') {
        const input = group.querySelector('.log-input');
        if (input) {
            input.focus();
            e.preventDefault();
        }
    }
}
```

#### `src/habit_tracker/templates/base.html`

**Add Log-specific CSS** (in the `<style>` section):

```css
/* Log habit styles */
.log-entries {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
}

.log-entry {
    display: flex;
    gap: 0.5rem;
    align-items: flex-start;
    background: var(--pico-card-background-color, #2a2a2a);
    padding: 0.5rem;
    border-radius: 0.25rem;
}

.log-time {
    width: 5.5rem;
    padding: 0.25rem 0.5rem;
    font-family: monospace;
    font-size: 0.85rem;
}

.log-text {
    flex: 1;
    padding: 0.25rem 0.5rem;
    font-size: 0.9rem;
    resize: none;
    overflow: hidden;
    min-height: 1.5rem;
    line-height: 1.4;
}

.log-delete {
    background: none;
    border: none;
    color: var(--pico-muted-color);
    cursor: pointer;
    padding: 0.25rem 0.5rem;
    font-size: 1.2rem;
    line-height: 1;
    border-radius: 0.25rem;
}

.log-delete:hover {
    color: #ef4444;
    background: rgba(239, 68, 68, 0.1);
}

.add-log-row {
    display: flex;
    gap: 0.5rem;
}

.add-log-row .log-input {
    flex: 1;
}

.add-log-row button {
    padding: 0.5rem 1rem;
}

.log-count {
    font-size: 0.75rem;
    color: var(--pico-muted-color);
    margin-top: 0.5rem;
}

.empty-state {
    color: var(--pico-muted-color);
    font-style: italic;
    padding: 1rem;
    text-align: center;
    background: var(--pico-card-background-color, #2a2a2a);
    border-radius: 0.25rem;
}
```

### Success Criteria

#### Automated Verification:
- [x] Tests pass: `make test`
- [x] Lint passes: `make fix`

#### Manual Verification:
- [ ] Run `make dev`, create a Log habit
- [ ] Go to daily entry view (/)
- [ ] Log habit shows with empty state
- [ ] Type text and click Add - entry appears with current time
- [ ] Press Enter in input - adds entry and keeps focus
- [ ] Press A when habit focused - focuses input
- [ ] Edit timestamp - auto-saves
- [ ] Edit text - auto-expands textarea, auto-saves
- [ ] Click delete (×) - removes entry, auto-saves
- [ ] Entry count updates correctly
- [ ] Page reload preserves all entries

---

## Phase 7: Calendar View

### Overview
Log habits should show color_filled on calendar for days with any entries.

### Changes Required

The `_get_entry_color()` function was already updated in Phase 2. The calendar view will work automatically since it uses this function.

### Success Criteria

#### Automated Verification:
- [x] Tests pass: `make test`

#### Manual Verification:
- [ ] Run `make dev`, create a Log habit with entries
- [ ] Go to calendar view for the Log habit
- [ ] Days with entries show color_filled (green by default)
- [ ] Days without entries show gray
- [ ] No legend appears (log habits don't have options)

---

## Testing Strategy

### New Tests to Write:

**Model tests** (`tests/test_models.py`):
- LogHabit creation with defaults
- LogHabit with custom color
- LogEntry creation with items
- LogEntry empty list (valid)
- LogItem validation (empty text fails)
- LogEntry max 100 items limit
- Discriminated union deserialization includes log type

**Route tests** (`tests/test_main.py`):
- POST /habits creates log habit
- POST /save parses JSON log data correctly
- POST /save handles malformed JSON gracefully
- PUT /habits/{id} updates log habit name and color
- GET / renders log habit entry form
- Calendar view shows correct colors for log habit

### Edge Cases:
- Empty log entries array (valid, renders empty state)
- Malformed JSON in form field (defaults to empty array)
- 100 items exactly (valid, at limit)
- 101 items (validation error - but shouldn't happen from UI)
- Entries with empty text (filtered out during save)
- Timestamps at midnight (00:00)
- Very long text entries (textarea expands)

## Code References

- `src/habit_tracker/models.py:85-93` - Habit discriminated union
- `src/habit_tracker/models.py:143-151` - HabitEntry discriminated union
- `src/habit_tracker/main.py:45-75` - `_get_entry_color()` function
- `src/habit_tracker/main.py:126-149` - `/save` endpoint match statement
- `src/habit_tracker/main.py:184-209` - `POST /habits` creation
- `src/habit_tracker/main.py:510-563` - `PUT /habits/{habit_id}` update
- `src/habit_tracker/templates/index.html:76-94` - Multi-select template (pattern to follow)
- `src/habit_tracker/templates/habits.html:32-39` - Type dropdown
- `src/habit_tracker/templates/edit_habit.html:62-69` - Journal/Time color section
- `docs/research/log-habit-mockup.html` - UI mockup with CSS and JS patterns

## Open Questions

None - all design decisions documented in research docs.
