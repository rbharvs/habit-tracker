from datetime import date, time
from typing import Annotated, Literal

from pydantic import BaseModel, Field, NonNegativeInt

# Constrained types for habit fields
HabitId = Annotated[str, Field(min_length=1)]
HabitName = Annotated[str, Field(min_length=1)]
NonEmptyOptions = Annotated[
    list[str],
    Field(min_length=1, max_length=9, description="1-9 options (keyboard shortcuts)"),
]

# =============================================================================
# Habit Definitions (discriminated union by "type" field)
# =============================================================================


class BinaryHabit(BaseModel):
    """A yes/no habit (e.g., 'Did you work out?')"""

    type: Literal["binary"] = "binary"
    id: HabitId
    name: HabitName
    archived: bool = False


class SingleSelectHabit(BaseModel):
    """A habit with mutually exclusive options (e.g., mood: great/good/okay/bad)"""

    type: Literal["single_select"] = "single_select"
    id: HabitId
    name: HabitName
    options: NonEmptyOptions
    archived: bool = False


class JournalHabit(BaseModel):
    """A free-form text habit (e.g., daily notes)"""

    type: Literal["journal"] = "journal"
    id: HabitId
    name: HabitName
    archived: bool = False


class NumericHabit(BaseModel):
    """A numeric habit tracking nonnegative integers (e.g., glasses of water)."""

    type: Literal["numeric"] = "numeric"
    id: HabitId
    name: HabitName
    unit: str = ""  # e.g., "glasses", "pages"
    archived: bool = False


class TimeHabit(BaseModel):
    """A time-of-day habit (e.g., bedtime, wake time)."""

    type: Literal["time"] = "time"
    id: HabitId
    name: HabitName
    archived: bool = False


class MultiSelectHabit(BaseModel):
    """A habit with multiple selectable options (e.g., which exercises)."""

    type: Literal["multi_select"] = "multi_select"
    id: HabitId
    name: HabitName
    options: NonEmptyOptions
    archived: bool = False


# Discriminated union: Pydantic uses "type" field to determine which model
Habit = Annotated[
    BinaryHabit
    | SingleSelectHabit
    | JournalHabit
    | NumericHabit
    | TimeHabit
    | MultiSelectHabit,
    Field(discriminator="type"),
]

# =============================================================================
# Habit Entries (discriminated union by "type" field)
# =============================================================================


class BinaryEntry(BaseModel):
    """Entry for a binary habit"""

    type: Literal["binary"] = "binary"
    value: bool


class SingleSelectEntry(BaseModel):
    """Entry for a single-select habit"""

    type: Literal["single_select"] = "single_select"
    value: str  # The selected option


class JournalEntry(BaseModel):
    """Entry for a journal habit"""

    type: Literal["journal"] = "journal"
    value: str  # Free-form text


class NumericEntry(BaseModel):
    """Entry for a numeric habit."""

    type: Literal["numeric"] = "numeric"
    value: NonNegativeInt  # Enforced >= 0 at runtime by Pydantic


class TimeEntry(BaseModel):
    """Entry for a time habit."""

    type: Literal["time"] = "time"
    value: time


class MultiSelectEntry(BaseModel):
    """Entry for a multi-select habit."""

    type: Literal["multi_select"] = "multi_select"
    value: list[str]  # Selected options (can be empty)


# Discriminated union for entries
HabitEntry = Annotated[
    BinaryEntry
    | SingleSelectEntry
    | JournalEntry
    | NumericEntry
    | TimeEntry
    | MultiSelectEntry,
    Field(discriminator="type"),
]

# =============================================================================
# Daily Entries Container
# =============================================================================


class DailyEntries(BaseModel):
    """All habit entries for a single day."""

    date: date
    entries: dict[str, HabitEntry]  # habit_id -> entry
