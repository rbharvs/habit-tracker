"""Tests for Pydantic models with discriminated unions."""

from datetime import date

from pydantic import TypeAdapter


def test_binary_habit_creation():
    """BinaryHabit can be created with required fields."""
    from habit_tracker.models import BinaryHabit

    habit = BinaryHabit(id="workout", name="Did you work out?")
    assert habit.type == "binary"
    assert habit.id == "workout"
    assert habit.name == "Did you work out?"


def test_single_select_habit_requires_options():
    """SingleSelectHabit requires options list."""
    from habit_tracker.models import SingleSelectHabit

    habit = SingleSelectHabit(
        id="mood", name="How was your mood?", options=["great", "good", "okay", "bad"]
    )
    assert habit.type == "single_select"
    assert habit.options == ["great", "good", "okay", "bad"]


def test_journal_habit_creation():
    """JournalHabit can be created with required fields."""
    from habit_tracker.models import JournalHabit

    habit = JournalHabit(id="notes", name="Notes")
    assert habit.type == "journal"


def test_habit_discriminated_union_deserialization():
    """Habit union deserializes correctly based on type field."""
    from habit_tracker.models import BinaryHabit, Habit, SingleSelectHabit

    adapter = TypeAdapter(list[Habit])

    data = [
        {"type": "binary", "id": "workout", "name": "Workout"},
        {
            "type": "single_select",
            "id": "mood",
            "name": "Mood",
            "options": ["good", "bad"],
        },
    ]

    habits = adapter.validate_python(data)
    assert len(habits) == 2
    assert isinstance(habits[0], BinaryHabit)
    assert isinstance(habits[1], SingleSelectHabit)


def test_binary_entry_creation():
    """BinaryEntry holds a boolean value."""
    from habit_tracker.models import BinaryEntry

    entry = BinaryEntry(value=True)
    assert entry.type == "binary"
    assert entry.value is True


def test_single_select_entry_creation():
    """SingleSelectEntry holds a string value."""
    from habit_tracker.models import SingleSelectEntry

    entry = SingleSelectEntry(value="good")
    assert entry.type == "single_select"
    assert entry.value == "good"


def test_journal_entry_creation():
    """JournalEntry holds a string value."""
    from habit_tracker.models import JournalEntry

    entry = JournalEntry(value="Had a great day!")
    assert entry.type == "journal"
    assert entry.value == "Had a great day!"


def test_habit_entry_discriminated_union():
    """HabitEntry union deserializes correctly based on type field."""
    from habit_tracker.models import BinaryEntry, HabitEntry, JournalEntry

    adapter = TypeAdapter(dict[str, HabitEntry])

    data = {
        "workout": {"type": "binary", "value": True},
        "notes": {"type": "journal", "value": "Great workout today"},
    }

    entries = adapter.validate_python(data)
    assert isinstance(entries["workout"], BinaryEntry)
    assert isinstance(entries["notes"], JournalEntry)


def test_daily_entries_creation():
    """DailyEntries holds date and entries dict."""
    from habit_tracker.models import BinaryEntry, DailyEntries

    daily = DailyEntries(
        date=date(2025, 1, 5), entries={"workout": BinaryEntry(value=True)}
    )
    assert daily.date == date(2025, 1, 5)
    assert daily.entries["workout"].value is True


def test_daily_entries_serialization_roundtrip():
    """DailyEntries can be serialized and deserialized."""
    from habit_tracker.models import BinaryEntry, DailyEntries, JournalEntry

    original = DailyEntries(
        date=date(2025, 1, 5),
        entries={
            "workout": BinaryEntry(value=True),
            "notes": JournalEntry(value="Test notes"),
        },
    )

    # Serialize to dict (as would happen with JSON)
    data = original.model_dump()

    # Deserialize back
    restored = DailyEntries(**data)

    assert restored.date == original.date
    assert restored.entries["workout"].value is True
    assert restored.entries["notes"].value == "Test notes"
