# Research: Creating a New "Log" Habit Type

**Date**: 2026-01-03T03:04:20Z
**Git Commit**: 9e07056a6a239ba92f069330cdefb74e81fbc7ba
**Branch**: main

## Research Question

How would you create a new "Log" habit type? This will be a structured list, each with a timestamp and text field. Starts empty and then you can add new logs.

## Summary

The codebase uses a discriminated union pattern with Pydantic models for habit types. Each habit type requires:
1. A habit definition model (e.g., `LogHabit`)
2. A corresponding entry model (e.g., `LogEntry`)
3. Addition to the `Habit` and `HabitEntry` discriminated unions
4. Handler in `main.py` for form submission (`/save` endpoint)
5. Handler in `main.py` for habit creation (`POST /habits` endpoint)
6. Handler in `main.py` for habit update (`PUT /habits/{habit_id}` endpoint)
7. Color calculation in `_get_entry_color()` function
8. Template rendering in `index.html` (daily entry form)
9. Template rendering in `edit_habit.html` (habit configuration)
10. Template rendering in `habits.html` (habit creation form type option)

The Log type is unique because it requires a **list of log items** rather than a single value, making it similar in complexity to `MultiSelectHabit` but with structured sub-items (timestamp + text).

## Detailed Findings

### 1. Models Layer (`src/habit_tracker/models.py`)

#### Existing Habit Type Pattern
All habit types follow this structure:
- A Pydantic `BaseModel` subclass with a `type: Literal["..."]` discriminator field
- Common fields: `id`, `name`, `archived`
- Type-specific fields (colors, options, units, etc.)

**Example: JournalHabit** (`models.py:41-48`)
```python
class JournalHabit(BaseModel):
    """A free-form text habit (e.g., daily notes)"""

    type: Literal["journal"] = "journal"
    id: HabitId
    name: HabitName
    archived: bool = False
    color_filled: str = "#22c55e"  # green
```

#### Existing Entry Type Pattern
Entry types parallel habit types:
- A Pydantic `BaseModel` with `type: Literal["..."]`
- A `value` field with type-appropriate data

**Example: MultiSelectEntry** (`models.py:135-139`) - closest to Log's list structure
```python
class MultiSelectEntry(BaseModel):
    """Entry for a multi-select habit."""

    type: Literal["multi_select"] = "multi_select"
    value: list[str]  # Selected options (can be empty)
```

#### Discriminated Unions
Both `Habit` and `HabitEntry` are defined as annotated unions with `discriminator="type"`:

**Habit union** (`models.py:85-93`)
```python
Habit = Annotated[
    BinaryHabit
    | SingleSelectHabit
    | JournalHabit
    | NumericHabit
    | TimeHabit
    | MultiSelectHabit,
    Field(discriminator="type"),
]
```

**HabitEntry union** (`models.py:143-151`)
```python
HabitEntry = Annotated[
    BinaryEntry
    | SingleSelectEntry
    | JournalEntry
    | NumericEntry
    | TimeEntry
    | MultiSelectEntry,
    Field(discriminator="type"),
]
```

### 2. Storage Layer (`src/habit_tracker/storage/`)

#### Protocol Definition (`protocol.py:7-18`)
Storage is abstracted via `StorageProtocol`:
```python
class StorageProtocol(Protocol):
    def load_habits(self) -> list[Habit]: ...
    def save_habits(self, habits: list[Habit]) -> None: ...
    def load_entries(self, day: date) -> DailyEntries | None: ...
    def save_entries(self, entries: DailyEntries) -> None: ...
    ...
```

#### JSON Serialization (`json_storage.py:47-49`)
Entries are serialized using Pydantic's `model_dump()`:
```python
def save_entries(self, entries: DailyEntries) -> None:
    path = self.entries_dir / f"{entries.date.isoformat()}.json"
    path.write_text(json.dumps(entries.model_dump(), indent=2, default=str))
```

Since Pydantic handles nested models, a `LogEntry` with a list of log items will serialize automatically.

### 3. API Endpoints (`src/habit_tracker/main.py`)

#### Entry Save Endpoint (`main.py:108-162`)
The `/save` POST endpoint uses exhaustive pattern matching:
```python
match habit:
    case BinaryHabit():
        entries[habit.id] = BinaryEntry(value=field_name in form)
    case SingleSelectHabit():
        ...
    case MultiSelectHabit():
        selected = form.getlist(field_name)
        entries[habit.id] = MultiSelectEntry(value=[str(v) for v in selected])
    case _ as unreachable:
        assert_never(unreachable)
```

A Log type would need a new case that parses multiple form fields (e.g., `habit_{id}_text_0`, `habit_{id}_text_1`, etc.) or uses a different submission mechanism.

#### Habit Creation (`main.py:176-227`)
The `POST /habits` endpoint creates habits based on type:
```python
match habit_type:
    case "binary":
        new_habit = BinaryHabit(id=habit_id, name=habit_name)
    case "numeric":
        unit = str(form.get("unit", ""))
        new_habit = NumericHabit(id=habit_id, name=habit_name, unit=unit)
    ...
```

#### Habit Update (`main.py:486-576`)
The `PUT /habits/{habit_id}` endpoint handles type-specific updates:
```python
match habit:
    case JournalHabit():
        color_filled = str(form.get("color_filled", habit.color_filled))
        ...
        updates["color_filled"] = color_filled
    case NumericHabit():
        updates["unit"] = unit
        updates["target_value"] = target_value
        updates["color_target"] = color_target
    ...
```

#### Color Calculation (`main.py:42-75`)
The `_get_entry_color()` function calculates calendar display colors:
```python
def _get_entry_color(habit: Habit, entry: HabitEntry) -> str:
    match habit:
        case JournalHabit():
            if isinstance(entry, JournalEntry) and entry.value.strip():
                return habit.color_filled
        case NumericHabit():
            if isinstance(entry, NumericEntry) and entry.value > 0:
                ...
                return habit.color_target
        ...
```

### 4. Frontend Templates

#### Daily Entry Form (`templates/index.html:16-96`)
Type-specific rendering via Jinja conditionals:
```html
{% if habit.type == "binary" %}
    <input type="checkbox" name="habit_{{ habit.id }}" ...>
{% elif habit.type == "journal" %}
    <textarea name="habit_{{ habit.id }}" rows="3">...</textarea>
{% elif habit.type == "multi_select" %}
    {% for option in habit.options %}
    <input type="checkbox" name="habit_{{ habit.id }}" value="{{ option }}" ...>
    {% endfor %}
{% endif %}
```

For a Log type, this would need a dynamic list of text inputs with an "Add" button, likely requiring JavaScript for adding new log entries.

#### Habit Creation Form (`templates/habits.html:30-39`)
Type selection dropdown:
```html
<select name="type" id="habit-type" onchange="toggleUnitField()">
    <option value="binary">Binary (Yes/No)</option>
    <option value="single_select">Single Select</option>
    <option value="multi_select">Multi Select</option>
    <option value="numeric">Numeric</option>
    <option value="time">Time</option>
    <option value="journal">Journal</option>
</select>
```

#### Habit Edit Form (`templates/edit_habit.html:28-87`)
Type-specific configuration fields:
```html
{% if habit.type == "binary" %}
    <input type="color" name="color_yes" ...>
    <input type="color" name="color_no" ...>
{% elif habit.type == "journal" or habit.type == "time" %}
    <input type="color" name="color_filled" ...>
{% elif habit.type == "numeric" %}
    <input type="text" name="unit" ...>
    <input type="number" name="target_value" ...>
    <input type="color" name="color_target" ...>
{% endif %}
```

#### Keyboard Shortcuts (`templates/index.html:132-177`)
Type-specific keyboard handling (Log would likely have none):
```javascript
if (habitType === 'binary') {
    // Y/N keys toggle checkbox
} else if (habitType === 'single_select') {
    // 1-9 keys select radio
} else if (habitType === 'multi_select') {
    // 1-9 keys toggle checkboxes
}
```

### 5. Color Utilities (`src/habit_tracker/colors.py`)

Default color constant and utility functions:
- `DEFAULT_GRAY = "#e5e5e5"` - used when no entry exists
- `blend_colors()` - averages RGB for multi-select
- `interpolate_color()` - gradient for numeric habits
- `get_option_color()` - retrieves color from option_colors dict

## Code References

| File | Lines | Description |
|------|-------|-------------|
| `src/habit_tracker/models.py` | 1-163 | All model definitions and unions |
| `src/habit_tracker/models.py` | 41-48 | JournalHabit (simple reference pattern) |
| `src/habit_tracker/models.py` | 73-81 | MultiSelectHabit (list-based pattern) |
| `src/habit_tracker/models.py` | 135-139 | MultiSelectEntry (list value pattern) |
| `src/habit_tracker/models.py` | 85-93 | Habit discriminated union |
| `src/habit_tracker/models.py` | 143-151 | HabitEntry discriminated union |
| `src/habit_tracker/main.py` | 42-75 | `_get_entry_color()` function |
| `src/habit_tracker/main.py` | 108-162 | `/save` endpoint entry creation |
| `src/habit_tracker/main.py` | 176-227 | `POST /habits` habit creation |
| `src/habit_tracker/main.py` | 486-576 | `PUT /habits/{habit_id}` habit update |
| `src/habit_tracker/storage/protocol.py` | 7-18 | StorageProtocol interface |
| `src/habit_tracker/storage/json_storage.py` | 40-49 | Entry load/save (Pydantic serialization) |
| `src/habit_tracker/templates/index.html` | 16-96 | Type-specific entry rendering |
| `src/habit_tracker/templates/habits.html` | 30-39 | Type dropdown in creation form |
| `src/habit_tracker/templates/edit_habit.html` | 28-87 | Type-specific edit fields |

## Architecture Notes

### Discriminated Union Pattern
The codebase uses Pydantic discriminated unions with exhaustive pattern matching (`assert_never`). This pattern:
- Ensures type safety at runtime via Pydantic validation
- Enables exhaustive handling in match statements (compiler will error if a case is missing)
- Requires all types in the union to have a unique `type` literal field

### Form Submission Model
The app uses HTMX for partial page updates with auto-save:
- Form fields named `habit_{habit_id}` (or `habit_{habit_id}_suffix` for multi-value)
- Auto-save on change via JavaScript event listeners
- HTMX POST returns "Saved!" indicator instead of redirect

### Log Type Complexity
Unlike existing types, Log requires:
1. **Nested structure**: Each log item has timestamp + text, not just a simple value
2. **Dynamic list**: Users add/remove items; length varies per entry
3. **Client-generated timestamps**: Timestamps captured when user adds entry
4. **Append-only UI**: Existing logs shouldn't be easily deleted

This is more complex than any existing type. Closest analogs:
- `MultiSelectEntry.value: list[str]` - has list structure but homogeneous items
- `JournalEntry.value: str` - has text but no structure

## Design Decisions

1. **Timestamp source**: Client-generated on creation, but **editable** by user. Defaults to current time when adding a new entry.

2. **Log item structure**: Separate Pydantic model `LogItem` with `timestamp: time` and `text: str` fields.

3. **Edit behavior**: Users **can edit** both text and timestamp of existing log entries.

4. **Delete behavior**: Users **can delete** individual log items.

5. **Form encoding**: **JSON string in hidden field** (Option A).
   - Integrates with existing auto-save pattern
   - Clean server-side parsing with Pydantic
   - Avoids index-parsing headaches with deletions
   - JS already required for add/delete/edit UI

6. **Calendar visualization**: Any log entries = `color_filled` (simple boolean: has entries or not).

7. **Maximum entries per day**: 100 entries per day limit.

8. **Keyboard shortcuts**:
   - Press **A** when habit-group focused → focuses input for typing
   - Press **Enter** in input → adds entry, clears input, keeps focus for rapid entry
   - Keyboard hint: "Press A to add"

## Proposed Implementation

### Models (`models.py`)

```python
class LogItem(BaseModel):
    """A single log entry with timestamp and text."""
    timestamp: time
    text: str = Field(min_length=1)


class LogHabit(BaseModel):
    """A log habit for timestamped text entries."""

    type: Literal["log"] = "log"
    id: HabitId
    name: HabitName
    archived: bool = False
    color_filled: str = "#22c55e"  # green


class LogEntry(BaseModel):
    """Entry for a log habit."""

    type: Literal["log"] = "log"
    value: list[LogItem] = Field(default_factory=list, max_length=100)
```

### Form Encoding Pattern

```html
<!-- Hidden field holds JSON array of log items -->
<input type="hidden" name="habit_{{ habit.id }}" id="habit_{{ habit.id }}_data"
       value="{{ entries.get(habit.id).value | tojson if entries.get(habit.id) else '[]' }}">

<!-- Visible UI for interaction -->
<div class="log-entries" id="log_{{ habit.id }}_entries">
    {% for item in entries.get(habit.id).value %}
    <div class="log-entry">
        <input type="time" class="log-time" value="{{ item.timestamp.strftime('%H:%M') }}">
        <input type="text" class="log-text" value="{{ item.text }}">
        <button type="button" class="log-delete">&times;</button>
    </div>
    {% endfor %}
</div>
<div class="add-log-row">
    <input type="text" class="log-input" placeholder="Add a log entry...">
    <button type="button" onclick="addLogEntry('{{ habit.id }}')">Add</button>
</div>
```

### JavaScript Pattern

```javascript
// Serialize log entries to hidden field and trigger auto-save
function updateLogData(habitId) {
    const entries = document.querySelectorAll(`#log_${habitId}_entries .log-entry`);
    const items = Array.from(entries).map(entry => ({
        timestamp: entry.querySelector('.log-time').value,
        text: entry.querySelector('.log-text').value
    })).filter(item => item.text.trim());  // Remove empty entries

    document.getElementById(`habit_${habitId}_data`).value = JSON.stringify(items);
    document.querySelector('form').requestSubmit();  // Auto-save
}

// Add new log entry
function addLogEntry(habitId) {
    const input = document.querySelector(`#habit_${habitId} .log-input`);
    const text = input.value.trim();
    if (!text) return;

    const now = new Date();
    const timestamp = now.toTimeString().slice(0, 5);  // HH:MM

    // Create entry DOM element
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `
        <input type="time" class="log-time" value="${timestamp}">
        <input type="text" class="log-text" value="${text}">
        <button type="button" class="log-delete">&times;</button>
    `;

    document.getElementById(`log_${habitId}_entries`).appendChild(entry);
    input.value = '';
    input.focus();  // Keep focus for rapid entry

    updateLogData(habitId);
}

// Keyboard shortcut: A or Enter to focus input when habit-group focused
} else if (habitType === 'log') {
    if (key === 'a' || key === 'Enter') {
        const input = group.querySelector('.log-input');
        input.focus();
        e.preventDefault();
    }
}

// Enter in log input adds entry (not form submit)
document.querySelectorAll('.log-input').forEach(input => {
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const habitId = input.closest('.habit-group').dataset.habitId;
            addLogEntry(habitId);
            e.preventDefault();
        }
    });
});
```

### Server-Side Parsing (`main.py`)

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

### Color Calculation

```python
case LogHabit():
    if isinstance(entry, LogEntry) and entry.value:
        return habit.color_filled
```
