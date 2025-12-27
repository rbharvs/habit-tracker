"""FastAPI app with routes for viewing/editing daily entries."""

from datetime import date, timedelta
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
    SingleSelectEntry,
    SingleSelectHabit,
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
    entries = storage.load_entries(target_date)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "date": target_date,
            "habits": habits,
            "entries": entries.entries if entries else {},
            "prev_date": (target_date - timedelta(days=1)).isoformat(),
            "next_date": (target_date + timedelta(days=1)).isoformat(),
            "is_today": target_date == date.today(),
        },
    )


@app.post("/save", response_model=None)
def save(request: Request, storage: Storage, form: FormDataDep) -> Response:
    """Save habit entries from form submission."""
    day = date.fromisoformat(str(form["date"]))
    habits = storage.load_habits()

    entries: dict[str, BinaryEntry | SingleSelectEntry | JournalEntry] = {}
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
