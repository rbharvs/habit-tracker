"""FastAPI app with routes for viewing/editing daily entries."""

import calendar as cal
from datetime import date, time, timedelta
from pathlib import Path
from typing import Annotated, assert_never

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.datastructures import FormData

from .colors import (
    DEFAULT_GRAY,
    blend_colors,
    get_option_color,
    interpolate_color,
)
from .models import (
    BinaryEntry,
    BinaryHabit,
    DailyEntries,
    Habit,
    HabitEntry,
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
from .storage import Storage

app = FastAPI()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


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


async def get_form_data(request: Request) -> FormData:
    """Parse form data asynchronously for use in sync routes."""
    return await request.form()


FormDataDep = Annotated[FormData, Depends(get_form_data)]


@app.get("/", response_class=HTMLResponse)
def index(request: Request, storage: Storage, day: str | None = None) -> HTMLResponse:
    """Show habit entry form for a day (defaults to today)."""
    target_date = date.fromisoformat(day) if day else date.today()
    habits = storage.load_habits()
    active_habits = [h for h in habits if not h.archived]
    entries = storage.load_entries(target_date)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "date": target_date,
            "habits": active_habits,
            "entries": entries.entries if entries else {},
            "prev_date": (target_date - timedelta(days=1)).isoformat(),
            "next_date": (target_date + timedelta(days=1)).isoformat(),
            "is_today": False,  # Computed client-side for timezone accuracy
        },
    )


@app.post("/save", response_model=None)
def save(request: Request, storage: Storage, form: FormDataDep) -> Response:
    """Save habit entries from form submission."""
    day = date.fromisoformat(str(form["date"]))
    habits = storage.load_habits()

    entries: dict[
        str,
        BinaryEntry
        | SingleSelectEntry
        | JournalEntry
        | NumericEntry
        | TimeEntry
        | MultiSelectEntry,
    ] = {}
    for habit in habits:
        field_name = f"habit_{habit.id}"
        # Exhaustive pattern matching with assert_never
        match habit:
            case BinaryHabit():
                entries[habit.id] = BinaryEntry(value=field_name in form)
            case SingleSelectHabit():
                if field_name in form:
                    entries[habit.id] = SingleSelectEntry(value=str(form[field_name]))
            case JournalHabit():
                entries[habit.id] = JournalEntry(value=str(form.get(field_name, "")))
            case NumericHabit():
                if field_name in form:
                    raw = str(form[field_name]).strip()
                    if raw:
                        entries[habit.id] = NumericEntry(value=int(raw))
            case TimeHabit():
                if field_name in form:
                    raw = str(form[field_name]).strip()
                    if raw:
                        entries[habit.id] = TimeEntry(value=time.fromisoformat(raw))
            case MultiSelectHabit():
                # Multiple checkboxes with same name come as getlist
                selected = form.getlist(field_name)
                entries[habit.id] = MultiSelectEntry(value=[str(v) for v in selected])
            case _ as unreachable:
                assert_never(unreachable)

    storage.save_entries(DailyEntries(date=day, entries=entries))

    # If HTMX request, return just a success indicator with timestamp tooltip
    if request.headers.get("HX-Request"):
        from datetime import datetime

        timestamp = datetime.now().strftime("%H:%M:%S")
        html = f'<span class="saved-indicator show" title="Saved at {timestamp}">'
        html += "Saved!</span>"
        return HTMLResponse(html)

    return RedirectResponse(url=f"./?day={day.isoformat()}", status_code=303)


@app.get("/habits", response_class=HTMLResponse)
def list_habits(request: Request, storage: Storage) -> HTMLResponse:
    """Show habit management page."""
    habits = storage.load_habits()
    return templates.TemplateResponse(
        request,
        "habits.html",
        {"habits": habits},
    )


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
            options = [
                str(o).strip() for o in str(form["options"]).split(",") if o.strip()
            ]
            new_habit = SingleSelectHabit(id=habit_id, name=habit_name, options=options)
        case "journal":
            new_habit = JournalHabit(id=habit_id, name=habit_name)
        case "numeric":
            unit = str(form.get("unit", ""))
            new_habit = NumericHabit(id=habit_id, name=habit_name, unit=unit)
        case "time":
            new_habit = TimeHabit(id=habit_id, name=habit_name)
        case "multi_select":
            options = [
                str(o).strip() for o in str(form["options"]).split(",") if o.strip()
            ]
            new_habit = MultiSelectHabit(id=habit_id, name=habit_name, options=options)
        case _:
            return HTMLResponse("Invalid habit type", status_code=400)

    habits = storage.load_habits()
    # Check for duplicate ID
    if any(h.id == habit_id for h in habits):
        return HTMLResponse("Habit ID already exists", status_code=400)

    habits.append(new_habit)
    storage.save_habits(habits)

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request, "partials/habit_list.html", {"habits": habits}
        )

    return RedirectResponse(url="./habits", status_code=303)


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
        archived_habit = habit.model_copy(update={"archived": True})
        habits[habit_idx] = archived_habit

    storage.save_habits(habits)

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request, "partials/habit_list.html", {"habits": habits}
        )

    return RedirectResponse(url="./habits", status_code=303)


@app.post("/habits/{habit_id}/move-up")
def move_habit_up(
    request: Request,
    storage: Storage,
    habit_id: str,
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
def move_habit_down(
    request: Request,
    storage: Storage,
    habit_id: str,
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


@app.get("/habits/{habit_id}/entry-count")
def get_entry_count(storage: Storage, habit_id: str) -> dict[str, int]:
    """Get the number of entries for a habit (for delete confirmation)."""
    count = storage.count_entries_for_habit(habit_id)
    return {"count": count}


# =============================================================================
# Calendar View Routes
# =============================================================================


@app.get("/calendar", response_class=HTMLResponse)
def calendar_redirect(request: Request, storage: Storage) -> Response:
    """Redirect to calendar for first habit."""
    habits = storage.load_habits()
    active_habits = [h for h in habits if not h.archived]
    if not active_habits:
        # No habits, show empty state
        return templates.TemplateResponse(
            request,
            "calendar.html",
            {
                "habit": None,
                "habits": [],
                "calendar_weeks": [],
                "year": date.today().year,
                "month": date.today().month,
            },
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
    # Each week is 7 items, each item is a dict with day info
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

            # Calculate color based on habit type and entry
            color = DEFAULT_GRAY
            if entry is not None and current_date <= today:
                color = _get_entry_color(habit, entry)

            week.append(
                {
                    "date": current_date,
                    "day": current_date.day,
                    "is_current_month": current_date.month == month,
                    "is_today": current_date == today,
                    "is_future": current_date > today,
                    "entry": entry,
                    "color": color,
                }
            )
        calendar_weeks.append(week)

        # Stop if we've passed the end of the month
        if week[-1]["date"] > last_day and week[-1]["date"].month != month:
            break

    # Build legend for option-based habits
    legend = None
    match habit:
        case SingleSelectHabit() | MultiSelectHabit():
            legend = [
                {
                    "option": opt,
                    "color": get_option_color(opt, habit.option_colors, habit.options),
                }
                for opt in habit.options
            ]
        case _:
            pass

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
        request,
        "calendar.html",
        {
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
        },
    )


# =============================================================================
# Habit Edit Routes
# =============================================================================


@app.get("/habits/{habit_id}/edit", response_class=HTMLResponse)
def edit_habit_form(request: Request, storage: Storage, habit_id: str) -> HTMLResponse:
    """Edit form for a habit."""
    habits = storage.load_habits()
    habit = next((h for h in habits if h.id == habit_id), None)

    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")

    return templates.TemplateResponse(request, "edit_habit.html", {"habit": habit})


@app.put("/habits/{habit_id}", response_model=None)
def update_habit(
    request: Request,
    storage: Storage,
    habit_id: str,
    form: FormDataDep,
) -> Response:
    """Update a habit's editable fields."""
    habits = storage.load_habits()
    habit_idx = next((i for i, h in enumerate(habits) if h.id == habit_id), None)

    if habit_idx is None:
        raise HTTPException(status_code=404, detail="Habit not found")

    habit: Habit = habits[habit_idx]

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

        case SingleSelectHabit():
            updates.update(_update_select_habit(form, habit.options))

        case MultiSelectHabit():
            updates.update(_update_select_habit(form, habit.options))

        case JournalHabit():
            color_filled = str(form.get("color_filled", habit.color_filled))
            if not _is_valid_hex_color(color_filled):
                raise HTTPException(status_code=400, detail="Invalid color format")
            updates["color_filled"] = color_filled

        case TimeHabit():
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
                        raise HTTPException(
                            status_code=400, detail="Target must be positive"
                        )
                    updates["target_value"] = target_value
                except ValueError:
                    raise HTTPException(
                        status_code=400, detail="Invalid target value"
                    ) from None
            else:
                updates["target_value"] = None

            color_target = str(form.get("color_target", habit.color_target))
            if not _is_valid_hex_color(color_target):
                raise HTTPException(status_code=400, detail="Invalid color format")
            updates["color_target"] = color_target

        case _ as unreachable:  # pragma: no cover
            assert_never(unreachable)  # type: ignore[type-assertion-failure]

    # Apply updates
    updated_habit = habit.model_copy(update=updates)
    habits[habit_idx] = updated_habit
    storage.save_habits(habits)

    # Response based on request type
    is_htmx = request.headers.get("HX-Request")
    if is_htmx:
        # Return saved status for autosave (no redirect)
        return HTMLResponse("Saved")
    else:
        return RedirectResponse(url="..", status_code=303)


def _is_valid_hex_color(color: str) -> bool:
    """Validate hex color format (#RRGGBB)."""
    if not color.startswith("#") or len(color) != 7:
        return False
    try:
        int(color[1:], 16)
        return True
    except ValueError:
        return False


def _update_select_habit(form: FormData, existing_options: list[str]) -> dict:
    """Build updates dict for single/multi-select habits."""
    # Get options from form (includes existing + new)
    new_options = [str(o).strip() for o in form.getlist("options") if str(o).strip()]

    # Validate: all existing options must be present (no deletion)
    for existing_opt in existing_options:
        if existing_opt not in new_options:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot remove existing option: {existing_opt}",
            )

    # Validate: max 9 options
    if len(new_options) > 9:
        raise HTTPException(status_code=400, detail="Maximum 9 options allowed")

    # Validate: unique options
    if len(new_options) != len(set(new_options)):
        raise HTTPException(status_code=400, detail="Options must be unique")

    # Build option_colors from form
    option_colors = {}
    for opt in new_options:
        color_key = f"option_color_{opt}"
        if color_key in form:
            color = str(form[color_key])
            if _is_valid_hex_color(color):
                option_colors[opt] = color

    return {"options": new_options, "option_colors": option_colors}
