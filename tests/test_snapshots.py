"""Snapshot tests for HTTP response regression testing.

These tests capture the exact HTML/JSON responses to detect unintended changes
during refactoring. Run `pytest --snapshot-update` to update snapshots after
intentional changes.
"""

from datetime import date

import pytest

from habit_tracker.models import (
    BinaryEntry,
    BinaryHabit,
    DailyEntries,
    JournalEntry,
    JournalHabit,
    SingleSelectEntry,
    SingleSelectHabit,
)

# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def sample_habits(test_storage):
    """Create a representative set of habits for snapshot tests."""
    habits = [
        BinaryHabit(id="workout", name="Did you work out?"),
        SingleSelectHabit(
            id="mood",
            name="How was your mood?",
            options=["Great", "Good", "Okay", "Bad"],
        ),
        JournalHabit(id="notes", name="Daily notes"),
    ]
    test_storage.save_habits(habits)
    return habits


@pytest.fixture
def sample_entries(test_storage, sample_habits):
    """Create sample entries for the test date."""
    entries = DailyEntries(
        date=date(2025, 1, 15),
        entries={
            "workout": BinaryEntry(value=True),
            "mood": SingleSelectEntry(value="Good"),
            "notes": JournalEntry(value="Test journal entry for snapshot."),
        },
    )
    test_storage.save_entries(entries)
    return entries


# =============================================================================
# Index Page Snapshots
# =============================================================================


class TestIndexPageSnapshots:
    """Snapshot tests for the daily entry form (GET /)."""

    def test_index_empty_state(
        self, test_storage, deterministic, snapshot_html, client
    ):
        """Index page with no habits shows empty state."""
        response = client.get("/?day=2025-01-15")
        assert response.status_code == 200
        assert response.text == snapshot_html

    def test_index_with_habits_no_entries(
        self, sample_habits, deterministic, snapshot_html, client
    ):
        """Index page with habits but no entries for the day."""
        response = client.get("/?day=2025-01-15")
        assert response.status_code == 200
        assert response.text == snapshot_html

    def test_index_with_entries(
        self, sample_entries, deterministic, snapshot_html, client
    ):
        """Index page with existing entries filled in."""
        response = client.get("/?day=2025-01-15")
        assert response.status_code == 200
        assert response.text == snapshot_html


# =============================================================================
# Habits Management Page Snapshots
# =============================================================================


class TestHabitsPageSnapshots:
    """Snapshot tests for the habit management page (GET /habits)."""

    def test_habits_empty_state(
        self, test_storage, deterministic, snapshot_html, client
    ):
        """Habits page with no habits shows empty state."""
        response = client.get("/habits")
        assert response.status_code == 200
        assert response.text == snapshot_html

    def test_habits_with_active_habits(
        self, sample_habits, deterministic, snapshot_html, client
    ):
        """Habits page listing active habits."""
        response = client.get("/habits")
        assert response.status_code == 200
        assert response.text == snapshot_html

    def test_habits_with_archived(
        self, sample_habits, test_storage, deterministic, snapshot_html, client
    ):
        """Habits page with mix of active and archived habits."""
        habits = test_storage.load_habits()
        habits[0].archived = True  # Archive the first habit
        test_storage.save_habits(habits)

        response = client.get("/habits")
        assert response.status_code == 200
        assert response.text == snapshot_html


# =============================================================================
# Edit Habit Page Snapshots
# =============================================================================


class TestEditHabitPageSnapshots:
    """Snapshot tests for the habit edit form (GET /habits/{id}/edit)."""

    def test_edit_binary_habit(
        self, sample_habits, deterministic, snapshot_html, client
    ):
        """Edit form for a binary habit."""
        response = client.get("/habits/workout/edit")
        assert response.status_code == 200
        assert response.text == snapshot_html

    def test_edit_single_select_habit(
        self, sample_habits, deterministic, snapshot_html, client
    ):
        """Edit form for a single-select habit with options."""
        response = client.get("/habits/mood/edit")
        assert response.status_code == 200
        assert response.text == snapshot_html

    def test_edit_journal_habit(
        self, sample_habits, deterministic, snapshot_html, client
    ):
        """Edit form for a journal habit."""
        response = client.get("/habits/notes/edit")
        assert response.status_code == 200
        assert response.text == snapshot_html


# =============================================================================
# Calendar Page Snapshots
# =============================================================================


class TestCalendarPageSnapshots:
    """Snapshot tests for the calendar view (GET /calendar/{id})."""

    def test_calendar_empty_month(
        self, sample_habits, deterministic, snapshot_html, client
    ):
        """Calendar view with no entries for the month."""
        response = client.get("/calendar/workout?year=2025&month=1")
        assert response.status_code == 200
        assert response.text == snapshot_html

    def test_calendar_with_entries(
        self, sample_entries, deterministic, snapshot_html, client
    ):
        """Calendar view with entries showing colored cells."""
        response = client.get("/calendar/workout?year=2025&month=1")
        assert response.status_code == 200
        assert response.text == snapshot_html

    def test_calendar_single_select_with_legend(
        self, sample_entries, deterministic, snapshot_html, client
    ):
        """Calendar for single-select habit shows color legend."""
        response = client.get("/calendar/mood?year=2025&month=1")
        assert response.status_code == 200
        assert response.text == snapshot_html


# =============================================================================
# JSON API Snapshots
# =============================================================================


class TestAPISnapshots:
    """Snapshot tests for JSON API endpoints."""

    def test_entry_count_empty(self, sample_habits, deterministic, snapshot, client):
        """Entry count returns zero when no entries exist."""
        response = client.get("/habits/workout/entry-count")
        assert response.status_code == 200
        assert response.json() == snapshot

    def test_entry_count_with_entries(
        self, sample_entries, deterministic, snapshot, client
    ):
        """Entry count returns correct count."""
        response = client.get("/habits/workout/entry-count")
        assert response.status_code == 200
        assert response.json() == snapshot
