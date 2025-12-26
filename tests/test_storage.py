"""Tests for JSON file storage operations."""

import shutil
from datetime import date
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def clean_test_data():
    """Use a test data directory and clean up after each test."""
    from habit_tracker import storage

    test_dir = Path("test_data")
    storage.DATA_DIR = test_dir
    storage.CONFIG_FILE = test_dir / "config.json"
    storage.ENTRIES_DIR = test_dir / "entries"
    yield
    shutil.rmtree(test_dir, ignore_errors=True)


def test_ensure_dirs_creates_directories():
    """ensure_dirs creates data and entries directories."""
    from habit_tracker import storage

    storage.ensure_dirs()
    assert storage.DATA_DIR.exists()
    assert storage.ENTRIES_DIR.exists()


def test_load_habits_returns_empty_list_when_no_config():
    """load_habits returns empty list when config.json doesn't exist."""
    from habit_tracker import storage

    habits = storage.load_habits()
    assert habits == []


def test_save_and_load_habits_roundtrip():
    """Habits can be saved and loaded."""
    from habit_tracker import storage
    from habit_tracker.models import BinaryHabit, SingleSelectHabit

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


def test_load_entries_returns_none_when_no_file():
    """load_entries returns None when date file doesn't exist."""
    from habit_tracker import storage

    entries = storage.load_entries(date(2025, 1, 5))
    assert entries is None


def test_save_and_load_entries_roundtrip():
    """Entries can be saved and loaded."""
    from habit_tracker import storage
    from habit_tracker.models import BinaryEntry, DailyEntries, JournalEntry

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


def test_entries_stored_in_dated_files():
    """Each day's entries are stored in a separate file."""
    from habit_tracker import storage
    from habit_tracker.models import BinaryEntry, DailyEntries

    day1 = DailyEntries(date=date(2025, 1, 5), entries={"a": BinaryEntry(value=True)})
    day2 = DailyEntries(date=date(2025, 1, 6), entries={"a": BinaryEntry(value=False)})

    storage.save_entries(day1)
    storage.save_entries(day2)

    # Verify files exist
    assert (storage.ENTRIES_DIR / "2025-01-05.json").exists()
    assert (storage.ENTRIES_DIR / "2025-01-06.json").exists()

    # Verify independent loading
    loaded1 = storage.load_entries(date(2025, 1, 5))
    loaded2 = storage.load_entries(date(2025, 1, 6))

    assert loaded1.entries["a"].value is True
    assert loaded2.entries["a"].value is False
