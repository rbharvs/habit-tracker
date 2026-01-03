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


def test_count_entries_for_habit(tmp_path: Path):
    """count_entries_for_habit counts daily files containing habit."""
    from habit_tracker.models import BinaryEntry, DailyEntries

    storage = JsonFileStorage(data_dir=tmp_path / "data")

    # Create entries for 3 different days with the habit
    for day_offset in range(3):
        daily = DailyEntries(
            date=date(2025, 1, 5 + day_offset),
            entries={"workout": BinaryEntry(value=True)},
        )
        storage.save_entries(daily)

    # Create 1 entry without the habit
    daily = DailyEntries(
        date=date(2025, 1, 10),
        entries={"other_habit": BinaryEntry(value=True)},
    )
    storage.save_entries(daily)

    count = storage.count_entries_for_habit("workout")
    assert count == 3


def test_count_entries_for_habit_empty(tmp_path: Path):
    """count_entries_for_habit returns 0 for nonexistent habit."""
    storage = JsonFileStorage(data_dir=tmp_path / "data")

    count = storage.count_entries_for_habit("nonexistent")
    assert count == 0


def test_delete_entries_for_habit(tmp_path: Path):
    """delete_entries_for_habit removes habit from all daily files."""
    from habit_tracker.models import BinaryEntry, DailyEntries

    storage = JsonFileStorage(data_dir=tmp_path / "data")

    # Create entries with multiple habits
    for day_offset in range(3):
        daily = DailyEntries(
            date=date(2025, 1, 5 + day_offset),
            entries={
                "workout": BinaryEntry(value=True),
                "meditation": BinaryEntry(value=True),
            },
        )
        storage.save_entries(daily)

    # Delete the workout habit entries
    storage.delete_entries_for_habit("workout")

    # Verify workout is gone but meditation remains
    for day_offset in range(3):
        loaded = storage.load_entries(date(2025, 1, 5 + day_offset))
        assert loaded is not None
        assert "workout" not in loaded.entries
        assert "meditation" in loaded.entries


def test_delete_entries_for_habit_returns_count(tmp_path: Path):
    """delete_entries_for_habit returns number of files modified."""
    from habit_tracker.models import BinaryEntry, DailyEntries

    storage = JsonFileStorage(data_dir=tmp_path / "data")

    # Create entries for 3 days
    for day_offset in range(3):
        daily = DailyEntries(
            date=date(2025, 1, 5 + day_offset),
            entries={"workout": BinaryEntry(value=True)},
        )
        storage.save_entries(daily)

    # Create 1 entry without the habit
    daily = DailyEntries(
        date=date(2025, 1, 10),
        entries={"other_habit": BinaryEntry(value=True)},
    )
    storage.save_entries(daily)

    deleted_count = storage.delete_entries_for_habit("workout")
    assert deleted_count == 3


def test_save_and_load_habits_with_colors(tmp_path: Path):
    """Habits with color fields roundtrip through storage."""
    from habit_tracker.models import BinaryHabit, SingleSelectHabit

    storage = JsonFileStorage(data_dir=tmp_path / "data")
    habits = [
        BinaryHabit(
            id="workout", name="Workout", color_yes="#00ff00", color_no="#ff0000"
        ),
        SingleSelectHabit(
            id="mood",
            name="Mood",
            options=["good", "bad"],
            option_colors={"good": "#22c55e"},
        ),
    ]
    storage.save_habits(habits)
    loaded = storage.load_habits()

    assert loaded[0].color_yes == "#00ff00"
    assert loaded[1].option_colors == {"good": "#22c55e"}


def test_load_entries_range_returns_matching_dates(tmp_path: Path):
    """load_entries_range returns entries within date range."""
    from habit_tracker.models import BinaryEntry, DailyEntries

    storage = JsonFileStorage(data_dir=tmp_path / "data")

    # Create entries for 5 consecutive days
    for i in range(5):
        day = date(2025, 1, 10 + i)  # Jan 10-14
        storage.save_entries(
            DailyEntries(date=day, entries={"test": BinaryEntry(value=True)})
        )

    # Query middle 3 days
    result = storage.load_entries_range(date(2025, 1, 11), date(2025, 1, 13))

    assert len(result) == 3
    assert date(2025, 1, 11) in result
    assert date(2025, 1, 12) in result
    assert date(2025, 1, 13) in result
    assert date(2025, 1, 10) not in result
    assert date(2025, 1, 14) not in result


def test_load_entries_range_empty_returns_empty_dict(tmp_path: Path):
    """load_entries_range returns empty dict when no entries in range."""
    storage = JsonFileStorage(data_dir=tmp_path / "data")

    result = storage.load_entries_range(date(2025, 1, 1), date(2025, 1, 31))

    assert result == {}


def test_load_entries_range_partial_coverage(tmp_path: Path):
    """load_entries_range works when only some dates have entries."""
    from habit_tracker.models import BinaryEntry, DailyEntries

    storage = JsonFileStorage(data_dir=tmp_path / "data")

    # Create entries for only 2 of 5 days in range
    storage.save_entries(
        DailyEntries(date=date(2025, 1, 10), entries={"a": BinaryEntry(value=True)})
    )
    storage.save_entries(
        DailyEntries(date=date(2025, 1, 14), entries={"a": BinaryEntry(value=False)})
    )

    result = storage.load_entries_range(date(2025, 1, 10), date(2025, 1, 14))

    assert len(result) == 2
    assert result[date(2025, 1, 10)].entries["a"].value is True
    assert result[date(2025, 1, 14)].entries["a"].value is False
