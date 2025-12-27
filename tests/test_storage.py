"""Tests for JsonFileStorage class."""

from datetime import date
from pathlib import Path

from habit_tracker.storage.json_storage import JsonFileStorage


def test_creates_directories_on_init(tmp_path: Path):
    """JsonFileStorage creates data and entries directories on init."""
    data_dir = tmp_path / "data"
    storage = JsonFileStorage(data_dir=data_dir)

    assert data_dir.exists()
    assert storage.entries_dir.exists()


def test_load_habits_returns_empty_list_when_no_config(tmp_path: Path):
    """load_habits returns empty list when config.json doesn't exist."""
    storage = JsonFileStorage(data_dir=tmp_path / "data")
    habits = storage.load_habits()
    assert habits == []


def test_save_and_load_habits_roundtrip(tmp_path: Path):
    """Habits can be saved and loaded."""
    from habit_tracker.models import BinaryHabit, SingleSelectHabit

    storage = JsonFileStorage(data_dir=tmp_path / "data")
    habits = [
        BinaryHabit(id="workout", name="Did you work out?"),
        SingleSelectHabit(id="mood", name="Mood", options=["great", "good", "bad"]),
    ]

    storage.save_habits(habits)
    loaded = storage.load_habits()

    assert len(loaded) == 2
    assert loaded[0].id == "workout"
    assert loaded[0].type == "binary"
    assert loaded[1].id == "mood"
    assert loaded[1].type == "single_select"
    assert loaded[1].options == ["great", "good", "bad"]


def test_load_entries_returns_none_when_no_file(tmp_path: Path):
    """load_entries returns None when date file doesn't exist."""
    storage = JsonFileStorage(data_dir=tmp_path / "data")
    entries = storage.load_entries(date(2025, 1, 5))
    assert entries is None


def test_save_and_load_entries_roundtrip(tmp_path: Path):
    """Entries can be saved and loaded."""
    from habit_tracker.models import BinaryEntry, DailyEntries, JournalEntry

    storage = JsonFileStorage(data_dir=tmp_path / "data")
    daily = DailyEntries(
        date=date(2025, 1, 5),
        entries={
            "workout": BinaryEntry(value=True),
            "notes": JournalEntry(value="Great day!"),
        },
    )

    storage.save_entries(daily)
    loaded = storage.load_entries(date(2025, 1, 5))

    assert loaded is not None
    assert loaded.date == date(2025, 1, 5)
    assert loaded.entries["workout"].value is True
    assert loaded.entries["notes"].value == "Great day!"


def test_entries_stored_in_dated_files(tmp_path: Path):
    """Each day's entries are stored in a separate file."""
    from habit_tracker.models import BinaryEntry, DailyEntries

    storage = JsonFileStorage(data_dir=tmp_path / "data")
    day1 = DailyEntries(date=date(2025, 1, 5), entries={"a": BinaryEntry(value=True)})
    day2 = DailyEntries(date=date(2025, 1, 6), entries={"a": BinaryEntry(value=False)})

    storage.save_entries(day1)
    storage.save_entries(day2)

    # Verify files exist
    assert (storage.entries_dir / "2025-01-05.json").exists()
    assert (storage.entries_dir / "2025-01-06.json").exists()

    # Verify independent loading
    loaded1 = storage.load_entries(date(2025, 1, 5))
    loaded2 = storage.load_entries(date(2025, 1, 6))

    assert loaded1.entries["a"].value is True
    assert loaded2.entries["a"].value is False


def test_config_file_path(tmp_path: Path):
    """config_file property returns correct path."""
    storage = JsonFileStorage(data_dir=tmp_path / "data")
    assert storage.config_file == tmp_path / "data" / "config.json"


def test_entries_dir_path(tmp_path: Path):
    """entries_dir property returns correct path."""
    storage = JsonFileStorage(data_dir=tmp_path / "data")
    assert storage.entries_dir == tmp_path / "data" / "entries"
