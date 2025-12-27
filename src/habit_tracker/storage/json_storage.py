import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import TypeAdapter

from habit_tracker.models import DailyEntries, Habit


@dataclass
class JsonFileStorage:
    """JSON file-based storage implementation."""

    data_dir: Path

    def __post_init__(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.entries_dir.mkdir(exist_ok=True)

    @property
    def config_file(self) -> Path:
        return self.data_dir / "config.json"

    @property
    def entries_dir(self) -> Path:
        return self.data_dir / "entries"

    def load_habits(self) -> list[Habit]:
        if not self.config_file.exists():
            return []
        adapter = TypeAdapter(list[Habit])
        data = json.loads(self.config_file.read_text())
        return adapter.validate_python(data.get("habits", []))

    def save_habits(self, habits: list[Habit]) -> None:
        data = {"habits": [h.model_dump() for h in habits]}
        self.config_file.write_text(json.dumps(data, indent=2))

    def load_entries(self, day: date) -> DailyEntries | None:
        path = self.entries_dir / f"{day.isoformat()}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return DailyEntries(**data)

    def save_entries(self, entries: DailyEntries) -> None:
        path = self.entries_dir / f"{entries.date.isoformat()}.json"
        path.write_text(json.dumps(entries.model_dump(), indent=2, default=str))
