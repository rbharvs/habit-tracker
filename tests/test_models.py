"""Tests for Pydantic models with discriminated unions."""

from datetime import date, time

import pytest
from pydantic import TypeAdapter, ValidationError


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


# =============================================================================
# NumericHabit Tests
# =============================================================================


def test_numeric_habit_creation():
    """NumericHabit can be created with required fields."""
    from habit_tracker.models import NumericHabit

    habit = NumericHabit(id="water", name="Glasses of water", unit="glasses")
    assert habit.type == "numeric"
    assert habit.id == "water"
    assert habit.name == "Glasses of water"
    assert habit.unit == "glasses"


def test_numeric_habit_unit_optional():
    """NumericHabit unit defaults to empty string."""
    from habit_tracker.models import NumericHabit

    habit = NumericHabit(id="pushups", name="Push-ups")
    assert habit.unit == ""


def test_numeric_entry_creation():
    """NumericEntry holds an integer value."""
    from habit_tracker.models import NumericEntry

    entry = NumericEntry(value=8)
    assert entry.type == "numeric"
    assert entry.value == 8


def test_numeric_entry_rejects_negative():
    """NumericEntry rejects negative values at runtime."""
    from habit_tracker.models import NumericEntry

    with pytest.raises(ValidationError):
        NumericEntry(value=-1)


# =============================================================================
# TimeHabit Tests
# =============================================================================


def test_time_habit_creation():
    """TimeHabit can be created with required fields."""
    from habit_tracker.models import TimeHabit

    habit = TimeHabit(id="bedtime", name="Bedtime")
    assert habit.type == "time"
    assert habit.id == "bedtime"
    assert habit.name == "Bedtime"


def test_time_entry_creation():
    """TimeEntry holds a time value."""
    from habit_tracker.models import TimeEntry

    entry = TimeEntry(value=time(22, 30))
    assert entry.type == "time"
    assert entry.value == time(22, 30)


def test_time_entry_serialization():
    """TimeEntry serializes time as ISO 8601 string."""
    from habit_tracker.models import TimeEntry

    entry = TimeEntry(value=time(22, 30))
    data = entry.model_dump(mode="json")
    assert data["value"] == "22:30:00"


# =============================================================================
# MultiSelectHabit Tests
# =============================================================================


def test_multi_select_habit_creation():
    """MultiSelectHabit can be created with options."""
    from habit_tracker.models import MultiSelectHabit

    habit = MultiSelectHabit(
        id="exercises", name="Exercises", options=["cardio", "strength", "flexibility"]
    )
    assert habit.type == "multi_select"
    assert habit.options == ["cardio", "strength", "flexibility"]


def test_multi_select_entry_creation():
    """MultiSelectEntry holds a list of selected options."""
    from habit_tracker.models import MultiSelectEntry

    entry = MultiSelectEntry(value=["cardio", "strength"])
    assert entry.type == "multi_select"
    assert entry.value == ["cardio", "strength"]


def test_multi_select_entry_empty():
    """MultiSelectEntry can have empty selection."""
    from habit_tracker.models import MultiSelectEntry

    entry = MultiSelectEntry(value=[])
    assert entry.value == []


# =============================================================================
# Constraint Validation Tests
# =============================================================================


def test_habit_rejects_empty_id():
    """All habit types reject empty id."""
    from habit_tracker.models import BinaryHabit

    with pytest.raises(ValidationError):
        BinaryHabit(id="", name="Test")


def test_habit_rejects_empty_name():
    """All habit types reject empty name."""
    from habit_tracker.models import BinaryHabit

    with pytest.raises(ValidationError):
        BinaryHabit(id="test", name="")


def test_select_habit_allows_empty_options():
    """SingleSelectHabit and MultiSelectHabit allow empty options list."""
    from habit_tracker.models import MultiSelectHabit, SingleSelectHabit

    single = SingleSelectHabit(id="mood", name="Mood", options=[])
    assert single.options == []

    multi = MultiSelectHabit(id="exercises", name="Exercises", options=[])
    assert multi.options == []


def test_select_habit_rejects_more_than_9_options():
    """SingleSelectHabit and MultiSelectHabit reject more than 9 options."""
    from habit_tracker.models import MultiSelectHabit, SingleSelectHabit

    ten_options = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]

    with pytest.raises(ValidationError):
        SingleSelectHabit(id="rating", name="Rating", options=ten_options)

    with pytest.raises(ValidationError):
        MultiSelectHabit(id="tags", name="Tags", options=ten_options)


# =============================================================================
# Discriminated Union Tests for New Types
# =============================================================================


def test_habit_discriminated_union_with_new_types():
    """Habit union deserializes new types correctly."""
    from habit_tracker.models import Habit, MultiSelectHabit, NumericHabit, TimeHabit

    adapter = TypeAdapter(list[Habit])

    data = [
        {"type": "numeric", "id": "water", "name": "Water", "unit": "glasses"},
        {"type": "time", "id": "bedtime", "name": "Bedtime"},
        {
            "type": "multi_select",
            "id": "exercises",
            "name": "Exercises",
            "options": ["a", "b"],
        },
    ]

    habits = adapter.validate_python(data)
    assert len(habits) == 3
    assert isinstance(habits[0], NumericHabit)
    assert isinstance(habits[1], TimeHabit)
    assert isinstance(habits[2], MultiSelectHabit)


# =============================================================================
# Color Field Tests
# =============================================================================


def test_binary_habit_color_defaults():
    """BinaryHabit has default colors."""
    from habit_tracker.models import BinaryHabit

    habit = BinaryHabit(id="test", name="Test")
    assert habit.color_yes == "#22c55e"
    assert habit.color_no == "#ef4444"


def test_binary_habit_custom_colors():
    """BinaryHabit accepts custom colors."""
    from habit_tracker.models import BinaryHabit

    habit = BinaryHabit(id="test", name="Test", color_yes="#00ff00", color_no="#ff0000")
    assert habit.color_yes == "#00ff00"
    assert habit.color_no == "#ff0000"


def test_single_select_habit_option_colors_default_empty():
    """SingleSelectHabit option_colors defaults to empty dict."""
    from habit_tracker.models import SingleSelectHabit

    habit = SingleSelectHabit(id="mood", name="Mood", options=["good", "bad"])
    assert habit.option_colors == {}


def test_single_select_habit_with_option_colors():
    """SingleSelectHabit accepts option_colors mapping."""
    from habit_tracker.models import SingleSelectHabit

    habit = SingleSelectHabit(
        id="mood",
        name="Mood",
        options=["good", "bad"],
        option_colors={"good": "#22c55e", "bad": "#ef4444"},
    )
    assert habit.option_colors["good"] == "#22c55e"


def test_journal_habit_color_default():
    """JournalHabit has default color_filled."""
    from habit_tracker.models import JournalHabit

    habit = JournalHabit(id="notes", name="Notes")
    assert habit.color_filled == "#22c55e"


def test_numeric_habit_color_default():
    """NumericHabit has default color_target and None target_value."""
    from habit_tracker.models import NumericHabit

    habit = NumericHabit(id="water", name="Water")
    assert habit.color_target == "#22c55e"
    assert habit.target_value is None


def test_numeric_habit_with_target():
    """NumericHabit accepts target_value for gradient."""
    from habit_tracker.models import NumericHabit

    habit = NumericHabit(id="water", name="Water", target_value=8)
    assert habit.target_value == 8


def test_time_habit_color_default():
    """TimeHabit has default color_filled."""
    from habit_tracker.models import TimeHabit

    habit = TimeHabit(id="bedtime", name="Bedtime")
    assert habit.color_filled == "#22c55e"


def test_multi_select_habit_option_colors_default_empty():
    """MultiSelectHabit option_colors defaults to empty dict."""
    from habit_tracker.models import MultiSelectHabit

    habit = MultiSelectHabit(
        id="exercises", name="Exercises", options=["cardio", "strength"]
    )
    assert habit.option_colors == {}


def test_habit_loads_without_color_fields():
    """Habits deserialize correctly without color fields (backward compat)."""
    from habit_tracker.models import Habit

    adapter = TypeAdapter(list[Habit])
    data = [
        {"type": "binary", "id": "workout", "name": "Workout"},
        {
            "type": "single_select",
            "id": "mood",
            "name": "Mood",
            "options": ["good", "bad"],
        },
        {"type": "journal", "id": "notes", "name": "Notes"},
        {"type": "numeric", "id": "water", "name": "Water"},
        {"type": "time", "id": "bedtime", "name": "Bedtime"},
        {
            "type": "multi_select",
            "id": "exercises",
            "name": "Exercises",
            "options": ["a", "b"],
        },
    ]
    habits = adapter.validate_python(data)

    # All should have defaults
    assert habits[0].color_yes == "#22c55e"
    assert habits[1].option_colors == {}
    assert habits[2].color_filled == "#22c55e"
    assert habits[3].target_value is None
    assert habits[4].color_filled == "#22c55e"
    assert habits[5].option_colors == {}


def test_habit_color_roundtrip():
    """Habits with colors serialize and deserialize correctly."""
    from habit_tracker.models import BinaryHabit

    original = BinaryHabit(
        id="test", name="Test", color_yes="#aabbcc", color_no="#ddeeff"
    )
    data = original.model_dump()
    restored = BinaryHabit(**data)
    assert restored.color_yes == "#aabbcc"
    assert restored.color_no == "#ddeeff"
