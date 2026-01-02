# Implementation Plan: Habit Management Improvements

**Date**: 2026-01-02T01:46:29Z
**Git Commit**: 2c3e155ca1f31cdbcfcaaf302c8fa8adf948103b
**Branch**: main

## Overview

Add two improvements to the habit management experience:
1. **Reorder habits** - Allow users to change the display order of habits on the management page, with that order reflected on the daily entries form
2. **Navigation link** - Add a link from the entries page to the habits management page for easy access

## Current State

### Navigation
- Entries page (`index.html:4-12`) has date navigation but no link to habits page
- Habits page (`habits.html:4-8`) has "Back to Today" link using `.date-nav` styling pattern
- Navigation uses relative URLs (`./`, `?day=YYYY-MM-DD`)

### Habit Ordering
- Habits stored as ordered array in `data/config.json` (`json_storage.py:36-38`)
- Order preserved during load/save - array order = display order
- New habits appended to end (`main.py:167`)
- No explicit position field on habit models (`models.py:19-73`)
- Entries form iterates habits in order received (`index.html:17`)

### Habit List UI
- `partials/habit_list.html` renders habits with type badge, name, ID, and action buttons
- Uses HTMX for archive/delete with `#habit-list` target
- Existing actions: Archive button, Delete button

## Desired End State

1. **Entries page** has a "Manage Habits" link in the navigation bar
2. **Habits management page** displays move up/down buttons for each habit
3. **Habits appear in user-defined order** on both the management page and entries form
4. **Archived habits** remain at the bottom of the list (cannot be reordered until unarchived)

### Verification
- Navigate from entries page to habits page via link
- Reorder habits using move buttons
- Confirm new order persists after page refresh
- Confirm entries page shows habits in the new order

## What We're NOT Doing

- Drag-and-drop reordering (too complex for initial implementation)
- Unarchive functionality (separate feature)
- Position field on models (using implicit array index instead)
- Keyboard shortcuts for reordering

---

## Phase 1: Add Navigation Link to Entries Page

### Overview
Add a "Manage Habits" link to the entries page navigation bar, appearing on the right side when viewing today (replacing the empty span).

### Changes Required

#### `src/habit_tracker/templates/index.html:7-11`
**Changes**: Replace conditional Next/empty span with "Manage Habits" link on the right

```html
{% if not is_today %}
<a href="?day={{ next_date }}">Next &rarr;</a>
{% else %}
<a href="./habits">Manage Habits</a>
{% endif %}
```

### Success Criteria

#### Automated Verification:
- [x] Tests pass: `make test`
- [x] Type check passes: `make fix` (includes typecheck)

#### Manual Verification:
- [ ] On today's date: "Manage Habits" link appears on right side of nav
- [ ] On past dates: "Next" link still appears (existing behavior preserved)
- [ ] Clicking "Manage Habits" navigates to `/habits` page
- [ ] "Back to Today" link on habits page returns to entries page

---

## Phase 2: Add Reorder Endpoints

### Overview
Add two API endpoints to move habits up or down in the list. Uses HTMX pattern to return updated habit list partial.

### Changes Required

#### `src/habit_tracker/main.py`
**Changes**: Add POST endpoints for moving habits up/down

After the delete endpoint (around line 209), add:

```python
@app.post("/habits/{habit_id}/move-up")
async def move_habit_up(
    request: Request,
    habit_id: str,
    storage: StorageProtocol = Depends(get_storage),
) -> Response:
    """Move a habit up in the list (earlier position)."""
    habits = storage.load_habits()

    # Find habit index
    habit_idx = next((i for i, h in enumerate(habits) if h.id == habit_id), None)
    if habit_idx is None:
        raise HTTPException(status_code=404, detail="Habit not found")

    # Can't move up if already at top or habit is archived
    if habit_idx == 0 or habits[habit_idx].archived:
        # Return current list unchanged
        pass
    else:
        # Find previous non-archived habit to swap with
        prev_idx = habit_idx - 1
        while prev_idx >= 0 and habits[prev_idx].archived:
            prev_idx -= 1

        if prev_idx >= 0:
            habits[habit_idx], habits[prev_idx] = habits[prev_idx], habits[habit_idx]
            storage.save_habits(habits)

    # Return updated list
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request, "partials/habit_list.html", {"habits": habits}
        )
    return RedirectResponse(url="./habits", status_code=303)


@app.post("/habits/{habit_id}/move-down")
async def move_habit_down(
    request: Request,
    habit_id: str,
    storage: StorageProtocol = Depends(get_storage),
) -> Response:
    """Move a habit down in the list (later position)."""
    habits = storage.load_habits()

    # Find habit index
    habit_idx = next((i for i, h in enumerate(habits) if h.id == habit_id), None)
    if habit_idx is None:
        raise HTTPException(status_code=404, detail="Habit not found")

    # Can't move down if already at bottom or habit is archived
    if habit_idx == len(habits) - 1 or habits[habit_idx].archived:
        # Return current list unchanged
        pass
    else:
        # Find next non-archived habit to swap with
        next_idx = habit_idx + 1
        while next_idx < len(habits) and habits[next_idx].archived:
            next_idx += 1

        if next_idx < len(habits):
            habits[habit_idx], habits[next_idx] = habits[next_idx], habits[habit_idx]
            storage.save_habits(habits)

    # Return updated list
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request, "partials/habit_list.html", {"habits": habits}
        )
    return RedirectResponse(url="./habits", status_code=303)
```

### Success Criteria

#### Automated Verification:
- [x] Tests pass: `make test`
- [x] Type check passes: `make fix`

#### Manual Verification:
- [ ] POST `/habits/{id}/move-up` swaps habit with previous non-archived habit
- [ ] POST `/habits/{id}/move-down` swaps habit with next non-archived habit
- [ ] Moving first habit up has no effect
- [ ] Moving last habit down has no effect
- [ ] Archived habits cannot be moved

---

## Phase 3: Add Move Buttons to Habit List UI

### Overview
Add up/down arrow buttons to each non-archived habit in the list. Use HTMX for seamless updates.

### Changes Required

#### `src/habit_tracker/templates/partials/habit_list.html`
**Changes**: Add move buttons in `.habit-actions` div, before Archive/Delete buttons

```html
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
                hx-post="habits/{{ habit.id }}/move-up"
                hx-target="#habit-list"
                hx-swap="innerHTML"
                title="Move up">
            &uarr;
        </button>
        <button class="outline secondary"
                hx-post="habits/{{ habit.id }}/move-down"
                hx-target="#habit-list"
                hx-swap="innerHTML"
                title="Move down">
            &darr;
        </button>
        <button class="outline secondary"
                hx-delete="habits/{{ habit.id }}"
                ...existing attributes...>
            Archive
        </button>
        {% endif %}
        <button class="outline secondary delete-btn"
                ...existing attributes...>
            Delete
        </button>
    </div>
</li>
```

#### `src/habit_tracker/templates/base.html`
**Changes**: Add styling for move buttons (compact arrow buttons)

In the habit management styles section (around line 100-110), add:

```css
.habit-actions button.move-btn {
    padding: 0.25rem 0.5rem;
    min-width: auto;
}
```

Note: The arrow buttons will use `&uarr;` (↑) and `&darr;` (↓) HTML entities. If the `outline secondary` Pico CSS styling is sufficient, no additional CSS may be needed.

### Success Criteria

#### Automated Verification:
- [x] Tests pass: `make test`
- [x] Type check passes: `make fix`

#### Manual Verification:
- [ ] Each non-archived habit shows ↑ and ↓ buttons
- [ ] Archived habits do not show move buttons
- [ ] Clicking ↑ moves habit up in list (instant HTMX update)
- [ ] Clicking ↓ moves habit down in list (instant HTMX update)
- [ ] Order persists after page refresh
- [ ] Entries page shows habits in new order

---

## Testing Strategy

### New Tests to Write

Add to `tests/test_main.py`:

```python
def test_move_habit_up(tmp_path: Path, client: TestClient) -> None:
    """Test moving a habit up in the list."""
    # Setup: Create 3 habits
    # Move second habit up
    # Assert: Order is now [habit2, habit1, habit3]

def test_move_habit_down(tmp_path: Path, client: TestClient) -> None:
    """Test moving a habit down in the list."""
    # Setup: Create 3 habits
    # Move first habit down
    # Assert: Order is now [habit2, habit1, habit3]

def test_move_first_habit_up_noop(tmp_path: Path, client: TestClient) -> None:
    """Moving first habit up should have no effect."""
    # Setup: Create 2 habits
    # Move first habit up
    # Assert: Order unchanged

def test_move_last_habit_down_noop(tmp_path: Path, client: TestClient) -> None:
    """Moving last habit down should have no effect."""
    # Setup: Create 2 habits
    # Move last habit down
    # Assert: Order unchanged

def test_move_nonexistent_habit_returns_404(client: TestClient) -> None:
    """Moving a nonexistent habit returns 404."""

def test_archived_habit_cannot_be_moved(tmp_path: Path, client: TestClient) -> None:
    """Archived habits cannot be moved."""
    # Setup: Create habit, archive it
    # Try to move it
    # Assert: Order unchanged

def test_habit_order_reflected_on_index(tmp_path: Path, client: TestClient) -> None:
    """Habits appear on index page in the reordered sequence."""
    # Setup: Create habits [A, B, C]
    # Reorder to [B, A, C]
    # GET /
    # Assert: B appears before A in HTML
```

### Edge Cases

- Moving when only one habit exists (no-op)
- Moving with mix of archived and active habits (skip archived in swap logic)
- Concurrent reorder requests (handled by atomic file save)
- Empty habits list (nothing to display)

---

## Code References

- `src/habit_tracker/templates/index.html:4-12` - Entries page navigation
- `src/habit_tracker/templates/habits.html:4-8` - Habits page navigation pattern
- `src/habit_tracker/templates/partials/habit_list.html:1-30` - Habit list partial
- `src/habit_tracker/main.py:178-209` - Delete endpoint pattern to follow
- `src/habit_tracker/storage/json_storage.py:36-38` - How habits are saved (preserves order)
- `tests/test_main.py:481-512` - Existing delete tests for test patterns
