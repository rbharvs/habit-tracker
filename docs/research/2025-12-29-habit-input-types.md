# Research: Habit Input Types for Numeric, Time, and Future Extensions

**Date**: 2025-12-29T23:29:23Z
**Git Commit**: 2000a0d732b9ab6bc8fb0e621362abd214880087
**Branch**: main

## Research Question

How should the habit tracker model and display:
- Habits that require a numeric field input (e.g., number of drinks)
- Habits that require a clock field input (e.g., went to bed at)
- Other habit input types that may be useful in the future

## Summary

The existing codebase uses Pydantic discriminated unions with a `type` field discriminator. This pattern extends naturally to new habit types. Each habit type requires:
1. A `*Habit` model defining the habit configuration
2. A `*Entry` model defining how values are stored
3. HTML template rendering in `index.html`
4. Form handling in `main.py`'s `/save` route

Key findings:
- **Numeric habits**: Use `int | float` with optional bounds, render with `<input type="number">`
- **Time habits**: Use `datetime.time` (Pydantic handles ISO 8601 serialization), render with `<input type="time">`
- **Future types**: Multi-select, rating/scale, duration, and counter are the most practical additions

## Detailed Findings

### Current Architecture

The existing pattern in `src/habit_tracker/models.py:37-39`:

```python
Habit = Annotated[
    BinaryHabit | SingleSelectHabit | JournalHabit, Field(discriminator="type")
]
```

Each habit type has:
- A `type: Literal[...]` field for discrimination
- Common fields: `id: str`, `name: str`
- Type-specific fields (e.g., `options: list[str]` for SingleSelectHabit)

Form handling in `src/habit_tracker/main.py:66-75` uses exhaustive `match`/`case` with `assert_never` for type safety.

Template rendering in `src/habit_tracker/templates/index.html:21-43` uses Jinja2 conditionals on `habit.type`.

---

### Numeric Habit

**Use Cases**: glasses of water, pages read, push-ups, hours worked, drinks consumed

**Model Structure**:
```python
class NumericHabit(BaseModel):
    type: Literal["numeric"] = "numeric"
    id: str
    name: str
    unit: str = ""           # e.g., "glasses", "pages"
    min_value: int = 0
    max_value: int | None = None  # Optional upper bound
    step_size: int = 1       # For increment buttons
    is_integer: bool = True  # True for counts, False for decimals

class NumericEntry(BaseModel):
    type: Literal["numeric"] = "numeric"
    value: int | float
```

**When to Use int vs float**:
| Use Case | Type | Reason |
|----------|------|--------|
| Counts (glasses, pages) | `int` | Can't have 2.5 glasses |
| Time precision (hours slept) | `float` | Allow 7.5 hours |
| Weight/measurements | `float` | Precision matters |
| Ratings/scales | `int` | Always whole numbers |

**HTML Rendering**:
```html
{% elif habit.type == "numeric" %}
<div class="numeric-input">
    <input type="number" name="habit_{{ habit.id }}"
           value="{{ entries.get(habit.id).value if entries.get(habit.id) else '' }}"
           min="{{ habit.min_value }}"
           {% if habit.max_value %}max="{{ habit.max_value }}"{% endif %}
           step="{{ habit.step_size }}">
    {% if habit.unit %}<span class="unit">{{ habit.unit }}</span>{% endif %}
</div>
```

**Mobile UI Options**:
1. **Native number input**: Opens numeric keypad on mobile
2. **Increment/decrement buttons**: Large touch targets (44x44px minimum)
3. **Slider** (`<input type="range">`): Good for bounded ranges like 1-10

**Form Handling**:
```python
case NumericHabit():
    if field_name in form:
        raw = form.get(field_name, "")
        if raw:
            value = int(raw) if habit.is_integer else float(raw)
            entries[habit.id] = NumericEntry(value=value)
```

---

### Time Habit

**Use Cases**: bedtime, wake time, started work, took medication

**Model Structure**:
```python
from datetime import time

class TimeHabit(BaseModel):
    type: Literal["time"] = "time"
    id: str
    name: str

class TimeEntry(BaseModel):
    type: Literal["time"] = "time"
    value: time  # Pydantic handles ISO 8601 serialization
```

**Storage Format**: Pydantic serializes `datetime.time` as ISO 8601 strings in JSON:
```json
{
  "bedtime": {
    "type": "time",
    "value": "22:30:00"
  }
}
```

**HTML Rendering**:
```html
{% elif habit.type == "time" %}
<input type="time" name="habit_{{ habit.id }}"
       value="{{ entries.get(habit.id).value.isoformat()[:5] if entries.get(habit.id) else '' }}">
```

The `[:5]` slice extracts "HH:MM" from "HH:MM:SS" for the HTML value attribute.

**Mobile Behavior**:
- iOS: Native wheel picker (excellent UX)
- Android: Clock face or wheel picker
- No custom JavaScript needed

**Timezone Considerations**:
- For single-user tracker: Store as naive time objects (no timezone)
- User interprets times in their local timezone
- For multi-user: Store user timezone separately in profile

**Form Handling**:
```python
case TimeHabit():
    if field_name in form:
        # Pydantic auto-converts "HH:MM" string to time object
        entries[habit.id] = TimeEntry(value=form[field_name])
```

---

### Other Recommended Habit Types

#### Multi-Select Habit (HIGH PRIORITY)

**Use Cases**: "Which exercises did you do?", "Which meals did you prepare?"

```python
class MultiSelectHabit(BaseModel):
    type: Literal["multi_select"] = "multi_select"
    id: str
    name: str
    options: list[str]

class MultiSelectEntry(BaseModel):
    type: Literal["multi_select"] = "multi_select"
    value: list[str]  # Can be empty, one, or many
```

**HTML**: Multiple checkboxes sharing the same `name` attribute.

**Why High Priority**: Extends existing SingleSelectHabit pattern with minimal changes. Very common use case (exercise routines, meal tracking).

---

#### Rating/Scale Habit (MEDIUM PRIORITY)

**Use Cases**: "Rate your mood 1-5", "Energy level today"

```python
class RatingHabit(BaseModel):
    type: Literal["rating"] = "rating"
    id: str
    name: str
    min_value: int = 1
    max_value: int = 5
    labels: dict[int, str] | None = None  # e.g., {1: "awful", 5: "great"}

class RatingEntry(BaseModel):
    type: Literal["rating"] = "rating"
    value: int
```

**HTML Options**:
1. Radio buttons with labels
2. Star rating (requires JavaScript)
3. Slider (`<input type="range">`) with value display

**Why Medium Priority**: Captures sentiment data that's more nuanced than binary but simpler than free text. Good for mood tracking.

---

#### Duration Habit (MEDIUM PRIORITY)

**Use Cases**: "How long did you exercise?", "Meditation duration"

```python
class DurationHabit(BaseModel):
    type: Literal["duration"] = "duration"
    id: str
    name: str
    unit: Literal["minutes", "hours", "seconds"] = "minutes"
    goal: int | None = None  # Optional goal for progress tracking

class DurationEntry(BaseModel):
    type: Literal["duration"] = "duration"
    value: int  # Always stored in base unit
```

**HTML**: Number input with unit label, or segmented inputs (hours + minutes).

**Why Medium Priority**: Time tracking is common for exercise, meditation, study habits. Enables analytics (total hours this week).

---

#### Counter/Tally Habit (MEDIUM PRIORITY)

**Use Cases**: Quick tallies throughout the day (water glasses, compliments given)

Structurally similar to NumericHabit but with UX optimized for rapid increment:

```python
class CounterHabit(BaseModel):
    type: Literal["counter"] = "counter"
    id: str
    name: str
    unit: str
    increment: int = 1

class CounterEntry(BaseModel):
    type: Literal["counter"] = "counter"
    value: int
```

**HTML**: Large +/- buttons with current count display. Auto-submits on each tap.

**Why Medium Priority**: Different UX focus than numeric (rapid taps vs. precise entry). Very popular in apps like Loop Habit Tracker.

---

#### Location Habit (LOW PRIORITY)

**Use Cases**: "Where did you work out?", "Work location today?"

Can be implemented as a SingleSelectHabit with predefined locations. Not a priority for MVP.

---

#### Compound/Sub-Item Habit (LOW PRIORITY)

**Use Cases**: "Workout (warmup, main set, cooldown)"

Requires nested storage schema. Recommend deferring—similar results achievable with multi-select.

---

## Code References

- `src/habit_tracker/models.py:11-39` - Current Habit discriminated union
- `src/habit_tracker/models.py:46-70` - Current HabitEntry discriminated union
- `src/habit_tracker/main.py:66-75` - Form handling with exhaustive match
- `src/habit_tracker/templates/index.html:21-43` - Template conditionals for habit types

## Architecture Notes

**Discriminated Union Pattern**: Each new habit type requires:
1. Add `*Habit` model with `type: Literal["..."]`
2. Add `*Entry` model with matching `type` literal
3. Extend the `Habit` and `HabitEntry` union types
4. Add `case *Habit():` in `main.py` route
5. Add `{% elif habit.type == "..." %}` in template

**Storage**: JSON structure in `data/entries/YYYY-MM-DD.json` handles all types without schema changes. Pydantic validates on deserialization.

**Mobile Considerations**: Native HTML5 inputs (`type="number"`, `type="time"`, `type="range"`) provide excellent mobile UX without custom JavaScript.

## Implementation Priority

| Type | Priority | Complexity | Notes |
|------|----------|------------|-------|
| Numeric | HIGH | Low | Native HTML, common use case |
| Time | HIGH | Low | Native HTML, Pydantic handles serialization |
| Multi-Select | HIGH | Low | Extends existing pattern |
| Rating | MEDIUM | Low | Good for mood/sentiment |
| Duration | MEDIUM | Medium | Time tracking, needs unit handling |
| Counter | MEDIUM | Medium | UX-focused variant of numeric |
| Location | LOW | Low | Can use SingleSelectHabit |
| Compound | LOW | High | Defer—complex nested storage |

## Open Questions

1. **Validation boundaries**: Should numeric/time habits validate on client-side only or also enforce server-side bounds?
2. **Default values**: Should habits have configurable defaults, or always start empty?
3. **Optional vs required**: Should some habits be marked as required for a day to be "complete"?
4. **Calendar visualization**: How should different types be color-coded in calendar view?
