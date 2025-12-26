from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field

# =============================================================================
# Habit Definitions (discriminated union by "type" field)
# =============================================================================


class BinaryHabit(BaseModel):
    """A yes/no habit (e.g., 'Did you work out?')"""

    type: Literal["binary"] = "binary"
    id: str
    name: str


class SingleSelectHabit(BaseModel):
    """A habit with mutually exclusive options (e.g., mood: great/good/okay/bad)"""

    type: Literal["single_select"] = "single_select"
    id: str
    name: str
    options: list[str]  # Required for this type


class JournalHabit(BaseModel):
    """A free-form text habit (e.g., daily notes)"""

    type: Literal["journal"] = "journal"
    id: str
    name: str


# Discriminated union: Pydantic uses "type" field to determine which model
Habit = Annotated[
    BinaryHabit | SingleSelectHabit | JournalHabit, Field(discriminator="type")
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


# Discriminated union for entries
HabitEntry = Annotated[
    BinaryEntry | SingleSelectEntry | JournalEntry, Field(discriminator="type")
]

# =============================================================================
# Daily Entries Container
# =============================================================================


class DailyEntries(BaseModel):
    """All habit entries for a single day."""

    date: date
    entries: dict[str, HabitEntry]  # habit_id -> entry
