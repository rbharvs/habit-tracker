import json
from datetime import date
from pathlib import Path

from pydantic import TypeAdapter

from .models import DailyEntries, Habit

DATA_DIR = Path("data")
CONFIG_FILE = DATA_DIR / "config.json"
ENTRIES_DIR = DATA_DIR / "entries"


def ensure_dirs() -> None:
    """Create data directories if they don't exist."""
    DATA_DIR.mkdir(exist_ok=True)
    ENTRIES_DIR.mkdir(exist_ok=True)


def load_habits() -> list[Habit]:
    """Load habit definitions from config."""
    if not CONFIG_FILE.exists():
        return []
    adapter = TypeAdapter(list[Habit])
    data = json.loads(CONFIG_FILE.read_text())
    return adapter.validate_python(data.get("habits", []))


def save_habits(habits: list[Habit]) -> None:
    """Save habit definitions to config."""
    ensure_dirs()
    data = {"habits": [h.model_dump() for h in habits]}
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


def load_entries(day: date) -> DailyEntries | None:
    """Load entries for a specific day."""
    path = ENTRIES_DIR / f"{day.isoformat()}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return DailyEntries(**data)


def save_entries(entries: DailyEntries) -> None:
    """Save entries for a specific day."""
    ensure_dirs()
    path = ENTRIES_DIR / f"{entries.date.isoformat()}.json"
    path.write_text(json.dumps(entries.model_dump(), indent=2, default=str))
