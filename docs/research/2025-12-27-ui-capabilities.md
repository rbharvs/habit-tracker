# Research: UI Capabilities for Keyboard Entry, Habit CRUD, and Calendar View

**Date**: 2025-12-27T20:00:08Z
**Git Commit**: 2000a0d732b9ab6bc8fb0e621362abd214880087
**Branch**: main

## Research Question

Can our current tech stack support the following in the UI:
- Full keyboard entry in the UI? (after tabbing to field, enter y/n for binary, 1-9 for single select)
- Habit CRUD (need to be careful about allowing modifications to habits after they have entries)
- Calendar view for each habit, with habit CRUD allowing color-coding in calendar view (like in Google Sheets) (e.g., for a binary, green for true, red for false; for a single select, can choose colors for each option)

## Summary

**Yes, the current tech stack (FastAPI + HTMX 2.0.4 + Jinja2 + PicoCSS + vanilla JS) can support all three features.** Here's the capability assessment:

| Feature | Supported | Notes |
|---------|-----------|-------|
| Keyboard entry (y/n, 1-9) | **Yes** | HTMX has native `hx-trigger` support for keyboard events with key filters |
| Habit CRUD | **Yes** | FastAPI routes needed; models already support persistence via `save_habits()` |
| Calendar view | **Yes** | CSS Grid + custom styling; storage layer needs date range queries |
| Color-coding | **Yes** | CSS custom properties or discrete color classes; model extension for color config |

---

## Detailed Findings

### 1. Keyboard Entry Support

#### Current State

The app already has basic keyboard handling in `src/habit_tracker/templates/base.html:36-49`:

```javascript
// Auto-save on change
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
```

#### HTMX Keyboard Capabilities

HTMX 2.0.4 provides native keyboard event support through `hx-trigger`:

```html
<!-- Binary habit: y/n keys while focused -->
<input type="checkbox" name="habit_workout"
       hx-trigger="keyup[key=='y'], keyup[key=='n']"
       hx-vals='js:{value: event.key === "y"}'
       hx-post="/save-field">

<!-- Single select: number keys 1-9 -->
<fieldset hx-trigger="keyup[key=='1'] from:closest .habit-group,
                      keyup[key=='2'] from:closest .habit-group"
          hx-vals='js:{value: parseInt(event.key)}'
          hx-post="/save-field">
```

**Key syntax patterns:**
- `hx-trigger="keyup[key=='y']"` - Trigger on specific key
- `from:body` - Listen globally instead of only when focused
- `hx-vals='js:{...}'` - Dynamic values based on event
- Multiple keys: separate with comma or use `||` in filter

**Limitations:**
- Focus management after DOM swaps (use Idiomorph extension for better preservation)
- No simplified `key:y` syntax—must use full filter expression `key=='y'`

### 2. Habit CRUD Operations

#### Current State

**Models** (`src/habit_tracker/models.py`):
- Three habit types: `BinaryHabit`, `SingleSelectHabit`, `JournalHabit`
- Discriminated unions using Pydantic's `Field(discriminator="type")`
- Each habit has: `type`, `id`, `name` (plus `options` for single select)

**Storage Protocol** (`src/habit_tracker/storage/protocol.py:7-13`):
```python
class StorageProtocol(Protocol):
    def load_habits(self) -> list[Habit]: ...
    def save_habits(self, habits: list[Habit]) -> None: ...
    def load_entries(self, day: date) -> DailyEntries | None: ...
    def save_entries(self, entries: DailyEntries) -> None: ...
```

**Current Routes** (`src/habit_tracker/main.py`):
- `GET /` - Load and display habits and entries
- `POST /save` - Save entries for a specific day
- **No habit CRUD routes exist yet**

#### What's Available vs. Needed

| Operation | Storage Method | FastAPI Route | Template |
|-----------|---------------|---------------|----------|
| Create habit | `save_habits()` | Needed | Needed |
| Read habits | `load_habits()` | Exists (in index) | Exists |
| Update habit | `save_habits()` | Needed | Needed |
| Delete habit | `save_habits()` | Needed | Needed |

**Entry-Habit Relationship Considerations:**

Habits link to entries via `habit_id` key in `DailyEntries.entries` dict. When modifying habits:

1. **Safe changes** (no entry impact):
   - Rename habit (`name` field)
   - Reorder habits (if ordering added)
   - Add new habit

2. **Dangerous changes** (orphan entries):
   - Delete habit (leaves orphan entries)
   - Change habit ID (breaks linkage)
   - Change habit type (entries become invalid)

3. **Type-specific changes**:
   - Modify `options` on `SingleSelectHabit` (existing entries may reference removed options)

**Implementation approach:**
- Add `has_entries(habit_id: str)` check to storage
- Warn/confirm before destructive operations
- Consider soft-delete (archive) vs. hard delete

### 3. Calendar View

#### Current State

**Day navigation exists** (`src/habit_tracker/templates/index.html:4-12`):
```html
<nav class="date-nav">
    <a href="?day={{ prev_date }}">&larr; Prev</a>
    <h2>{{ date.strftime('%A, %b %d') }}</h2>
    {% if not is_today %}
    <a href="?day={{ next_date }}">Next &rarr;</a>
    {% endif %}
</nav>
```

**Storage limitation** (`src/habit_tracker/storage/protocol.py`):
- Only `load_entries(day: date)` exists (single date)
- **No method for date range queries**

#### Calendar Grid Implementation

**CSS Grid approach (recommended):**

```css
.calendar-grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 4px;
}

.day {
    aspect-ratio: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--pico-border-radius);
}
```

**Python calendar module for data:**

```python
import calendar

def get_month_weeks(year: int, month: int) -> list[list[int]]:
    cal = calendar.Calendar(firstweekday=calendar.SUNDAY)
    return cal.monthdayscalendar(year, month)
    # Returns: [[0, 0, 0, 1, 2, 3, 4], [5, 6, 7, ...], ...]
```

**Storage extension needed:**

```python
# Add to StorageProtocol
def load_entries_range(self, start: date, end: date) -> dict[date, DailyEntries]:
    """Load entries for all dates in range."""
    ...

# JSON implementation
def load_entries_range(self, start: date, end: date) -> dict[date, DailyEntries]:
    result = {}
    for file in self.entries_dir.glob("*.json"):
        file_date = date.fromisoformat(file.stem)
        if start <= file_date <= end:
            result[file_date] = self.load_entries(file_date)
    return result
```

### 4. Color-Coding in Calendar

#### Approach Options

**Option A: CSS Custom Properties (Continuous Scale)**

```css
.day {
    --intensity: 0; /* Set from 0 to 1 based on completion */
    --hue: calc(120 * var(--intensity)); /* 0=red, 120=green */
    background: hsl(var(--hue), 50%, 80%);
}
```

```html
<div class="day" style="--intensity: {{ completion_rate }};">{{ day }}</div>
```

**Option B: Discrete Color Classes (GitHub-style)**

```css
.day.complete { background: #22c55e; color: white; }
.day.partial  { background: #fbbf24; }
.day.missed   { background: #ef4444; color: white; }
.day.empty    { background: transparent; }
```

**Option C: User-Defined Colors (Model Extension)**

Extend habit models to store colors:

```python
class BinaryHabit(BaseModel):
    type: Literal["binary"] = "binary"
    id: str
    name: str
    color_true: str = "#22c55e"   # Green for checked
    color_false: str = "#ef4444"  # Red for unchecked

class SingleSelectHabit(BaseModel):
    type: Literal["single_select"] = "single_select"
    id: str
    name: str
    options: list[str]
    option_colors: dict[str, str] = {}  # e.g., {"great": "#22c55e", "bad": "#ef4444"}
```

---

## Code References

- `src/habit_tracker/templates/base.html:36-49` - Existing keyboard handlers
- `src/habit_tracker/templates/index.html:4-12` - Date navigation
- `src/habit_tracker/templates/index.html:17-45` - Habit input rendering
- `src/habit_tracker/models.py:11-39` - Habit discriminated union types
- `src/habit_tracker/models.py:46-70` - Entry discriminated union types
- `src/habit_tracker/storage/protocol.py:7-13` - Storage interface
- `src/habit_tracker/storage/json_storage.py:29-49` - JSON file operations
- `src/habit_tracker/main.py:35-53` - Index route (loads habits/entries)
- `src/habit_tracker/main.py:56-88` - Save route (persists entries)

---

## Architecture Notes

### Current Tech Stack

| Component | Library | Version | CDN/Local |
|-----------|---------|---------|-----------|
| Backend | FastAPI | >=0.127.1 | Local |
| Templates | Jinja2 | >=3.1.6 | Local |
| Frontend interactivity | HTMX | 2.0.4 | CDN |
| CSS framework | PicoCSS | v2 | CDN |
| Storage | JSON files or DynamoDB | - | Local |

### Storage Pattern

```
data/
├── config.json           # All habit definitions
└── entries/
    ├── 2025-01-01.json   # Entries for Jan 1
    ├── 2025-01-02.json   # Entries for Jan 2
    └── ...
```

Habit-to-entry linkage: `DailyEntries.entries[habit_id]` references `Habit.id`

### HTMX Patterns in Use

1. Form submission with partial response (`hx-post`, `hx-target="#save-status"`)
2. Automatic save on input change (vanilla JS → `requestSubmit()`)
3. HTMX request detection (`request.headers.get("HX-Request")`)

---

## Open Questions

1. **Habit modification safety**: Should we allow changing habit type after entries exist? Or only name/options?

2. **Orphan entries**: When deleting a habit, should we:
   - Delete all associated entries (destructive)
   - Keep entries but hide them (archive)
   - Prevent deletion if entries exist (strict)

3. **Color storage**: Should colors be stored:
   - In the habit definition (per-habit colors)
   - In user settings (global theme)
   - As CSS-only configuration (no backend changes)

4. **Calendar scope**: Show calendar for:
   - One habit at a time (simpler)
   - All habits aggregated (completion %)
   - All habits side-by-side (more complex)

5. **Date range query optimization**: For DynamoDB, should we use:
   - GSI for date-based queries
   - Current single-table design with range queries on sort key
