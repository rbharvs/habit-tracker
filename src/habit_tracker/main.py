"""FastAPI app with routes for viewing/editing daily entries."""

from datetime import date, time, timedelta
from pathlib import Path
from typing import Annotated, assert_never

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from starlette.datastructures import FormData

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
from .storage import Storage

app = FastAPI()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


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


@app.get("/habits/{habit_id}/entry-count")
def get_entry_count(storage: Storage, habit_id: str) -> dict[str, int]:
    """Get the number of entries for a habit (for delete confirmation)."""
    count = storage.count_entries_for_habit(habit_id)
    return {"count": count}
