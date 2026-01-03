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

    def count_entries_for_habit(self, habit_id: str) -> int:
        """Count how many daily entry files contain an entry for this habit."""
        count = 0
        for file in self.entries_dir.glob("*.json"):
            data = json.loads(file.read_text())
            if habit_id in data.get("entries", {}):
                count += 1
        return count

    def delete_entries_for_habit(self, habit_id: str) -> int:
        """Delete entries for a habit from all daily files. Returns count deleted."""
        count = 0
        for file in self.entries_dir.glob("*.json"):
            data = json.loads(file.read_text())
            if habit_id in data.get("entries", {}):
                del data["entries"][habit_id]
                file.write_text(json.dumps(data, indent=2, default=str))
                count += 1
        return count

    def load_entries_range(self, start: date, end: date) -> dict[date, DailyEntries]:
        """Load all entries between start and end dates (inclusive)."""
        result: dict[date, DailyEntries] = {}

        # Iterate through all entry files
        for file_path in self.entries_dir.glob("*.json"):
            # Parse date from filename (YYYY-MM-DD.json)
            try:
                file_date = date.fromisoformat(file_path.stem)
            except ValueError:
                continue  # Skip invalid filenames

            # Check if within range
            if start <= file_date <= end:
                entries = self.load_entries(file_date)
                if entries is not None:
                    result[file_date] = entries

        return result
