"""Tests for FastAPI routes (main.py)."""

from datetime import date, time, timedelta

from fastapi.testclient import TestClient

from habit_tracker.main import app
from habit_tracker.models import (
    BinaryEntry,
    BinaryHabit,
    DailyEntries,
    JournalHabit,
    MultiSelectHabit,
    NumericHabit,
    SingleSelectHabit,
    TimeHabit,
)


def test_index_returns_html(test_storage):
    """GET / returns HTML response."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_index_shows_today_by_default(test_storage):
    """GET / without day param shows today's date."""
    client = TestClient(app)
    response = client.get("/")
    today = date.today()
    assert today.strftime("%b %d") in response.text


def test_index_accepts_day_param(test_storage):
    """GET /?day=2025-01-05 shows that date."""
    client = TestClient(app)
    response = client.get("/?day=2025-01-05")
    assert response.status_code == 200
    assert "Jan 05" in response.text


def test_index_shows_habits(test_storage):
    """GET / shows configured habits."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Did you work out?")])

    client = TestClient(app)
    response = client.get("/")
    assert "Did you work out?" in response.text


def test_index_shows_empty_form_when_no_habits(test_storage):
    """GET / shows empty form when no habits configured."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    # Form should still exist even with no habits
    assert "<form" in response.text


def test_save_creates_entry(test_storage):
    """POST /save creates entry for date."""
    test_storage.save_habits([BinaryHabit(id="test", name="Test")])

    client = TestClient(app)
    response = client.post(
        "/save",
        data={"date": "2025-01-05", "habit_test": "on"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "day=2025-01-05" in response.headers["location"]

    entries = test_storage.load_entries(date(2025, 1, 5))
    assert entries is not None
    assert entries.entries["test"].value is True


def test_save_binary_unchecked(test_storage):
    """POST /save without checkbox creates false entry."""
    test_storage.save_habits([BinaryHabit(id="test", name="Test")])

    client = TestClient(app)
    client.post("/save", data={"date": "2025-01-05"}, follow_redirects=False)

    entries = test_storage.load_entries(date(2025, 1, 5))
    assert entries.entries["test"].value is False


def test_save_single_select(test_storage):
    """POST /save with radio selection creates single select entry."""
    test_storage.save_habits(
        [SingleSelectHabit(id="mood", name="Mood", options=["good", "bad"])]
    )

    client = TestClient(app)
    client.post(
        "/save",
        data={"date": "2025-01-05", "habit_mood": "good"},
        follow_redirects=False,
    )

    entries = test_storage.load_entries(date(2025, 1, 5))
    assert entries.entries["mood"].value == "good"


def test_save_journal(test_storage):
    """POST /save with textarea creates journal entry."""
    test_storage.save_habits([JournalHabit(id="notes", name="Notes")])

    client = TestClient(app)
    client.post(
        "/save",
        data={"date": "2025-01-05", "habit_notes": "Great day!"},
        follow_redirects=False,
    )

    entries = test_storage.load_entries(date(2025, 1, 5))
    assert entries.entries["notes"].value == "Great day!"


def test_index_shows_existing_entries(test_storage):
    """GET / shows previously saved entries."""
    test_storage.save_habits([BinaryHabit(id="test", name="Test")])
    test_storage.save_entries(
        DailyEntries(date=date.today(), entries={"test": BinaryEntry(value=True)})
    )

    client = TestClient(app)
    response = client.get("/")
    # Checkbox should be checked
    assert "checked" in response.text


def test_date_navigation_links(test_storage):
    """Index page has prev/next date navigation links."""
    client = TestClient(app)
    response = client.get("/?day=2025-01-05")
    assert "day=2025-01-04" in response.text  # prev
    assert "day=2025-01-06" in response.text  # next


def test_next_link_rendered_with_js_hiding(test_storage):
    """Next link is always rendered; hiding is done client-side."""
    client = TestClient(app)
    today = date.today()
    tomorrow = today + timedelta(days=1)
    response = client.get(f"/?day={today.isoformat()}")
    # Link is rendered (hidden client-side via JavaScript)
    assert f"day={tomorrow.isoformat()}" in response.text
    assert 'id="next-link"' in response.text


def test_save_htmx_returns_indicator(test_storage):
    """POST /save with HX-Request header returns saved indicator instead of redirect."""
    test_storage.save_habits([BinaryHabit(id="test", name="Test")])

    client = TestClient(app)
    response = client.post(
        "/save",
        data={"date": "2025-01-05", "habit_test": "on"},
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )
    # Should return 200 with saved indicator, not 303 redirect
    assert response.status_code == 200
    assert "Saved!" in response.text
    assert "saved-indicator" in response.text


def test_save_htmx_indicator_has_timestamp_tooltip(test_storage):
    """POST /save with HX-Request header includes timestamp in title attribute."""
    test_storage.save_habits([BinaryHabit(id="test", name="Test")])

    client = TestClient(app)
    response = client.post(
        "/save",
        data={"date": "2025-01-05", "habit_test": "on"},
        headers={"HX-Request": "true"},
    )
    # Should have a title attribute with timestamp for mouseover
    assert 'title="Saved at' in response.text


def test_save_htmx_still_persists_data(test_storage):
    """POST /save with HX-Request header still saves data."""
    test_storage.save_habits([BinaryHabit(id="test", name="Test")])

    client = TestClient(app)
    client.post(
        "/save",
        data={"date": "2025-01-05", "habit_test": "on"},
        headers={"HX-Request": "true"},
    )

    # Verify data was saved
    entries = test_storage.load_entries(date(2025, 1, 5))
    assert entries is not None
    assert entries.entries["test"].value is True


def test_index_has_mobile_meta_tags(test_storage):
    """GET / includes mobile-friendly meta tags."""
    client = TestClient(app)
    response = client.get("/")
    # Check for PWA-friendly meta tags
    assert 'name="apple-mobile-web-app-capable"' in response.text
    assert 'name="theme-color"' in response.text


def test_index_has_save_button(test_storage):
    """GET / has a save button that works on mobile."""
    client = TestClient(app)
    response = client.get("/")
    assert '<button type="submit"' in response.text
    assert "Save" in response.text


def test_save_redirect_uses_relative_url(test_storage):
    """POST /save redirects with relative URL for API Gateway compatibility."""
    test_storage.save_habits([BinaryHabit(id="test", name="Test")])

    client = TestClient(app)
    response = client.post(
        "/save",
        data={"date": "2025-01-05", "habit_test": "on"},
        follow_redirects=False,
    )
    location = response.headers["location"]
    # Must be relative (starts with ./) not absolute (starts with /)
    assert location.startswith("./"), f"Expected relative URL, got: {location}"
    assert not location.startswith("/"), f"URL must not be absolute: {location}"


def test_template_uses_relative_urls(test_storage):
    """Template uses relative URLs for API Gateway stage prefix compatibility."""
    test_storage.save_habits([BinaryHabit(id="test", name="Test")])

    client = TestClient(app)
    response = client.get("/?day=2025-01-05")

    # Form action should be relative
    assert 'action="save"' in response.text, "Form action must be relative 'save'"
    assert 'action="/save"' not in response.text, "Form action must not be absolute"

    # Nav links should be relative (no leading slash)
    assert 'href="?day=' in response.text, "Nav links must be relative '?day='"
    assert 'href="/?day=' not in response.text, "Nav links must not be absolute"

    # HTMX post should be relative
    assert 'hx-post="save"' in response.text, "HTMX post must be relative 'save'"
    assert 'hx-post="/save"' not in response.text, "HTMX post must not be absolute"


# =============================================================================
# NumericHabit Route Tests
# =============================================================================


def test_save_numeric(test_storage):
    """POST /save with number creates numeric entry."""
    test_storage.save_habits([NumericHabit(id="water", name="Water", unit="glasses")])

    client = TestClient(app)
    client.post(
        "/save",
        data={"date": "2025-01-05", "habit_water": "8"},
        follow_redirects=False,
    )

    entries = test_storage.load_entries(date(2025, 1, 5))
    assert entries.entries["water"].value == 8


def test_save_numeric_empty(test_storage):
    """POST /save with empty numeric field creates no entry."""
    test_storage.save_habits([NumericHabit(id="water", name="Water")])

    client = TestClient(app)
    client.post(
        "/save",
        data={"date": "2025-01-05", "habit_water": ""},
        follow_redirects=False,
    )

    entries = test_storage.load_entries(date(2025, 1, 5))
    assert "water" not in entries.entries


def test_index_shows_numeric_habit(test_storage):
    """GET / shows numeric input with unit."""
    test_storage.save_habits(
        [NumericHabit(id="water", name="Glasses of water", unit="glasses")]
    )

    client = TestClient(app)
    response = client.get("/")
    assert 'type="number"' in response.text
    assert 'name="habit_water"' in response.text
    assert "glasses" in response.text


# =============================================================================
# TimeHabit Route Tests
# =============================================================================


def test_save_time(test_storage):
    """POST /save with time creates time entry."""
    test_storage.save_habits([TimeHabit(id="bedtime", name="Bedtime")])

    client = TestClient(app)
    client.post(
        "/save",
        data={"date": "2025-01-05", "habit_bedtime": "22:30"},
        follow_redirects=False,
    )

    entries = test_storage.load_entries(date(2025, 1, 5))
    assert entries.entries["bedtime"].value == time(22, 30)


def test_save_time_empty(test_storage):
    """POST /save with empty time field creates no entry."""
    test_storage.save_habits([TimeHabit(id="bedtime", name="Bedtime")])

    client = TestClient(app)
    client.post(
        "/save",
        data={"date": "2025-01-05", "habit_bedtime": ""},
        follow_redirects=False,
    )

    entries = test_storage.load_entries(date(2025, 1, 5))
    assert "bedtime" not in entries.entries


def test_index_shows_time_habit(test_storage):
    """GET / shows time input."""
    test_storage.save_habits([TimeHabit(id="bedtime", name="Bedtime")])

    client = TestClient(app)
    response = client.get("/")
    assert 'type="time"' in response.text
    assert 'name="habit_bedtime"' in response.text


# =============================================================================
# MultiSelectHabit Route Tests
# =============================================================================


def test_save_multi_select(test_storage):
    """POST /save with multiple checkboxes creates multi-select entry."""
    test_storage.save_habits(
        [
            MultiSelectHabit(
                id="exercises",
                name="Exercises",
                options=["cardio", "strength", "flexibility"],
            )
        ]
    )

    client = TestClient(app)
    client.post(
        "/save",
        data={"date": "2025-01-05", "habit_exercises": ["cardio", "strength"]},
        follow_redirects=False,
    )

    entries = test_storage.load_entries(date(2025, 1, 5))
    assert set(entries.entries["exercises"].value) == {"cardio", "strength"}


def test_save_multi_select_empty(test_storage):
    """POST /save with no checkboxes creates empty multi-select entry."""
    test_storage.save_habits(
        [
            MultiSelectHabit(
                id="exercises", name="Exercises", options=["cardio", "strength"]
            )
        ]
    )

    client = TestClient(app)
    client.post(
        "/save",
        data={"date": "2025-01-05"},
        follow_redirects=False,
    )

    entries = test_storage.load_entries(date(2025, 1, 5))
    assert entries.entries["exercises"].value == []


def test_index_shows_multi_select_habit(test_storage):
    """GET / shows checkboxes for multi-select options."""
    test_storage.save_habits(
        [
            MultiSelectHabit(
                id="exercises", name="Exercises", options=["cardio", "strength"]
            )
        ]
    )

    client = TestClient(app)
    response = client.get("/")
    assert 'type="checkbox"' in response.text
    assert 'value="cardio"' in response.text
    assert 'value="strength"' in response.text


# =============================================================================
# Habit CRUD Route Tests (Phase 2)
# =============================================================================


def test_list_habits_route(test_storage):
    """GET /habits returns habit list."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Did you work out?")])

    client = TestClient(app)
    response = client.get("/habits")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Did you work out?" in response.text


def test_create_binary_habit(test_storage):
    """POST /habits creates binary habit."""
    client = TestClient(app)
    response = client.post(
        "/habits",
        data={"type": "binary", "id": "workout", "name": "Did you work out?"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "./habits" in response.headers["location"]

    habits = test_storage.load_habits()
    assert len(habits) == 1
    assert habits[0].id == "workout"
    assert habits[0].name == "Did you work out?"
    assert habits[0].type == "binary"


def test_create_single_select_habit(test_storage):
    """POST /habits creates single select habit with options."""
    client = TestClient(app)
    response = client.post(
        "/habits",
        data={
            "type": "single_select",
            "id": "mood",
            "name": "How are you feeling?",
            "options": "great, good, okay, bad",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    habits = test_storage.load_habits()
    assert len(habits) == 1
    assert habits[0].type == "single_select"
    assert habits[0].options == ["great", "good", "okay", "bad"]


def test_create_habit_duplicate_id_fails(test_storage):
    """POST /habits with duplicate ID returns 400."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Existing")])

    client = TestClient(app)
    response = client.post(
        "/habits",
        data={"type": "binary", "id": "workout", "name": "Duplicate"},
    )
    assert response.status_code == 400


def test_soft_delete_habit(test_storage):
    """DELETE /habits/{id} archives habit."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    client = TestClient(app)
    response = client.delete("/habits/workout", follow_redirects=False)
    assert response.status_code == 303

    habits = test_storage.load_habits()
    assert len(habits) == 1
    assert habits[0].archived is True


def test_hard_delete_habit(test_storage):
    """DELETE /habits/{id}?hard=true removes habit and entries."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])
    test_storage.save_entries(
        DailyEntries(
            date=date(2025, 1, 5), entries={"workout": BinaryEntry(value=True)}
        )
    )

    client = TestClient(app)
    response = client.delete("/habits/workout?hard=true", follow_redirects=False)
    assert response.status_code == 303

    habits = test_storage.load_habits()
    assert len(habits) == 0

    # Entries should also be deleted
    entries = test_storage.load_entries(date(2025, 1, 5))
    assert entries is None or "workout" not in entries.entries


def test_archived_habits_hidden_from_index(test_storage):
    """GET / excludes archived habits."""
    test_storage.save_habits(
        [
            BinaryHabit(id="active", name="Active Habit"),
            BinaryHabit(id="archived", name="Archived Habit", archived=True),
        ]
    )

    client = TestClient(app)
    response = client.get("/")
    assert "Active Habit" in response.text
    assert "Archived Habit" not in response.text


def test_entry_count_endpoint(test_storage):
    """GET /habits/{id}/entry-count returns correct count."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])
    test_storage.save_entries(
        DailyEntries(
            date=date(2025, 1, 5), entries={"workout": BinaryEntry(value=True)}
        )
    )
    test_storage.save_entries(
        DailyEntries(
            date=date(2025, 1, 6), entries={"workout": BinaryEntry(value=True)}
        )
    )

    client = TestClient(app)
    response = client.get("/habits/workout/entry-count")
    assert response.status_code == 200
    assert response.json() == {"count": 2}


def test_delete_nonexistent_habit_returns_404(test_storage):
    """DELETE /habits/{id} for nonexistent habit returns 404."""
    client = TestClient(app)
    response = client.delete("/habits/nonexistent")
    assert response.status_code == 404


def test_create_habit_invalid_type_returns_400(test_storage):
    """POST /habits with invalid type returns 400."""
    client = TestClient(app)
    response = client.post(
        "/habits",
        data={"type": "invalid_type", "id": "test", "name": "Test"},
    )
    assert response.status_code == 400


# =============================================================================
# Habit Reorder Tests
# =============================================================================


def test_move_habit_up(test_storage):
    """Test moving a habit up in the list."""
    test_storage.save_habits(
        [
            BinaryHabit(id="habit1", name="Habit 1"),
            BinaryHabit(id="habit2", name="Habit 2"),
            BinaryHabit(id="habit3", name="Habit 3"),
        ]
    )

    client = TestClient(app)
    response = client.post("/habits/habit2/move-up", follow_redirects=False)
    assert response.status_code == 303

    habits = test_storage.load_habits()
    assert [h.id for h in habits] == ["habit2", "habit1", "habit3"]


def test_move_habit_down(test_storage):
    """Test moving a habit down in the list."""
    test_storage.save_habits(
        [
            BinaryHabit(id="habit1", name="Habit 1"),
            BinaryHabit(id="habit2", name="Habit 2"),
            BinaryHabit(id="habit3", name="Habit 3"),
        ]
    )

    client = TestClient(app)
    response = client.post("/habits/habit1/move-down", follow_redirects=False)
    assert response.status_code == 303

    habits = test_storage.load_habits()
    assert [h.id for h in habits] == ["habit2", "habit1", "habit3"]


def test_move_first_habit_up_noop(test_storage):
    """Moving first habit up should have no effect."""
    test_storage.save_habits(
        [
            BinaryHabit(id="habit1", name="Habit 1"),
            BinaryHabit(id="habit2", name="Habit 2"),
        ]
    )

    client = TestClient(app)
    response = client.post("/habits/habit1/move-up", follow_redirects=False)
    assert response.status_code == 303

    habits = test_storage.load_habits()
    assert [h.id for h in habits] == ["habit1", "habit2"]


def test_move_last_habit_down_noop(test_storage):
    """Moving last habit down should have no effect."""
    test_storage.save_habits(
        [
            BinaryHabit(id="habit1", name="Habit 1"),
            BinaryHabit(id="habit2", name="Habit 2"),
        ]
    )

    client = TestClient(app)
    response = client.post("/habits/habit2/move-down", follow_redirects=False)
    assert response.status_code == 303

    habits = test_storage.load_habits()
    assert [h.id for h in habits] == ["habit1", "habit2"]


def test_move_nonexistent_habit_returns_404(test_storage):
    """Moving a nonexistent habit returns 404."""
    client = TestClient(app)
    response = client.post("/habits/nonexistent/move-up")
    assert response.status_code == 404


def test_archived_habit_cannot_be_moved(test_storage):
    """Archived habits cannot be moved."""
    test_storage.save_habits(
        [
            BinaryHabit(id="habit1", name="Habit 1"),
            BinaryHabit(id="habit2", name="Habit 2", archived=True),
            BinaryHabit(id="habit3", name="Habit 3"),
        ]
    )

    client = TestClient(app)
    # Try to move archived habit up
    response = client.post("/habits/habit2/move-up", follow_redirects=False)
    assert response.status_code == 303

    habits = test_storage.load_habits()
    # Order should be unchanged
    assert [h.id for h in habits] == ["habit1", "habit2", "habit3"]


def test_move_up_skips_archived_habits(test_storage):
    """Moving up should skip over archived habits."""
    test_storage.save_habits(
        [
            BinaryHabit(id="habit1", name="Habit 1"),
            BinaryHabit(id="habit2", name="Habit 2", archived=True),
            BinaryHabit(id="habit3", name="Habit 3"),
        ]
    )

    client = TestClient(app)
    response = client.post("/habits/habit3/move-up", follow_redirects=False)
    assert response.status_code == 303

    habits = test_storage.load_habits()
    # Should swap with habit1, skipping archived habit2
    assert [h.id for h in habits] == ["habit3", "habit2", "habit1"]


def test_move_down_skips_archived_habits(test_storage):
    """Moving down should skip over archived habits."""
    test_storage.save_habits(
        [
            BinaryHabit(id="habit1", name="Habit 1"),
            BinaryHabit(id="habit2", name="Habit 2", archived=True),
            BinaryHabit(id="habit3", name="Habit 3"),
        ]
    )

    client = TestClient(app)
    response = client.post("/habits/habit1/move-down", follow_redirects=False)
    assert response.status_code == 303

    habits = test_storage.load_habits()
    # Should swap with habit3, skipping archived habit2
    assert [h.id for h in habits] == ["habit3", "habit2", "habit1"]


def test_habit_order_reflected_on_index(test_storage):
    """Habits appear on index page in the reordered sequence."""
    test_storage.save_habits(
        [
            BinaryHabit(id="habit_a", name="Habit A"),
            BinaryHabit(id="habit_b", name="Habit B"),
            BinaryHabit(id="habit_c", name="Habit C"),
        ]
    )

    client = TestClient(app)

    # Reorder: move B to top
    client.post("/habits/habit_b/move-up", follow_redirects=False)

    # Check index page shows B before A
    response = client.get("/")
    assert response.status_code == 200
    # B should appear before A in the HTML
    b_pos = response.text.find("Habit B")
    a_pos = response.text.find("Habit A")
    c_pos = response.text.find("Habit C")
    assert b_pos < a_pos < c_pos, "Habits should appear in order: B, A, C"


def test_move_habit_htmx_returns_partial(test_storage):
    """Moving habit with HX-Request returns partial HTML."""
    test_storage.save_habits(
        [
            BinaryHabit(id="habit1", name="Habit 1"),
            BinaryHabit(id="habit2", name="Habit 2"),
        ]
    )

    client = TestClient(app)
    response = client.post(
        "/habits/habit2/move-up",
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Habit 2" in response.text
    assert "Habit 1" in response.text


# =============================================================================
# Calendar View Tests (Phase 3)
# =============================================================================


def test_calendar_redirect_to_first_habit(test_storage):
    """GET /calendar redirects to first habit's calendar."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    client = TestClient(app)
    response = client.get("/calendar", follow_redirects=False)

    assert response.status_code == 303
    assert "./calendar/workout" in response.headers["location"]


def test_calendar_redirect_skips_archived(test_storage):
    """GET /calendar skips archived habits."""
    test_storage.save_habits(
        [
            BinaryHabit(id="archived_habit", name="Archived", archived=True),
            BinaryHabit(id="active_habit", name="Active"),
        ]
    )

    client = TestClient(app)
    response = client.get("/calendar", follow_redirects=False)

    assert response.status_code == 303
    assert "./calendar/active_habit" in response.headers["location"]


def test_calendar_no_habits_shows_empty(test_storage):
    """GET /calendar with no habits shows empty state."""
    client = TestClient(app)
    response = client.get("/calendar")

    assert response.status_code == 200
    assert "No habits configured" in response.text


def test_calendar_habit_view(test_storage):
    """GET /calendar/{habit_id} shows calendar grid."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    client = TestClient(app)
    response = client.get("/calendar/workout")

    assert response.status_code == 200
    assert "Workout" in response.text
    assert "Sun" in response.text  # Day headers
    assert "Mon" in response.text


def test_calendar_habit_not_found(test_storage):
    """GET /calendar/{habit_id} returns 404 for unknown habit."""
    client = TestClient(app)
    response = client.get("/calendar/nonexistent")

    assert response.status_code == 404


def test_calendar_month_navigation(test_storage):
    """GET /calendar/{habit_id}?year=X&month=Y shows specified month."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    client = TestClient(app)
    response = client.get("/calendar/workout?year=2025&month=6")

    assert response.status_code == 200
    assert "June" in response.text
    assert "2025" in response.text


def test_calendar_shows_entries(test_storage):
    """Calendar shows existing entries."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])
    test_storage.save_entries(
        DailyEntries(
            date=date(2025, 1, 15), entries={"workout": BinaryEntry(value=True)}
        )
    )

    client = TestClient(app)
    response = client.get("/calendar/workout?year=2025&month=1")

    assert response.status_code == 200
    # Entry data is present (we'll verify colors in Phase 4)
    assert "15" in response.text


def test_calendar_nav_links_use_correct_relative_paths(test_storage):
    """Calendar prev/next month links should not double the calendar path."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    client = TestClient(app)
    response = client.get("/calendar/workout?year=2025&month=6")

    # Links should be ./workout not ./calendar/workout
    # (since we're already at /calendar/workout)
    assert "./workout?year=2025&month=5" in response.text  # prev
    assert "./workout?year=2025&month=7" in response.text  # next
    # Should NOT have doubled path
    assert "./calendar/workout" not in response.text


def test_calendar_habit_selector_uses_correct_relative_paths(test_storage):
    """Calendar habit selector dropdown should not double the calendar path."""
    test_storage.save_habits(
        [
            BinaryHabit(id="workout", name="Workout"),
            BinaryHabit(id="meditation", name="Meditation"),
        ]
    )

    client = TestClient(app)
    response = client.get("/calendar/workout?year=2025&month=6")

    # Selector should navigate to ./{habit_id} not ./calendar/{habit_id}
    # The JavaScript uses: window.location.href='./' + this.value + '?year=...'
    assert "'./' + this.value" in response.text or '"./" + this.value' in response.text
    # Should NOT have ./calendar/ in the selector JavaScript
    assert "'./calendar/'" not in response.text
    assert '"./calendar/"' not in response.text


# =============================================================================
# Calendar Color Rendering Tests (Phase 4)
# =============================================================================


def test_calendar_binary_yes_color(test_storage):
    """Calendar shows correct color for binary yes entry."""
    test_storage.save_habits(
        [BinaryHabit(id="workout", name="Workout", color_yes="#00ff00")]
    )
    test_storage.save_entries(
        DailyEntries(
            date=date(2025, 1, 15), entries={"workout": BinaryEntry(value=True)}
        )
    )

    client = TestClient(app)
    response = client.get("/calendar/workout?year=2025&month=1")

    assert "#00ff00" in response.text


def test_calendar_binary_no_color(test_storage):
    """Calendar shows correct color for binary no entry."""
    test_storage.save_habits(
        [BinaryHabit(id="workout", name="Workout", color_no="#ff0000")]
    )
    test_storage.save_entries(
        DailyEntries(
            date=date(2025, 1, 15), entries={"workout": BinaryEntry(value=False)}
        )
    )

    client = TestClient(app)
    response = client.get("/calendar/workout?year=2025&month=1")

    assert "#ff0000" in response.text


def test_calendar_single_select_legend(test_storage):
    """Calendar shows legend for single-select habit."""
    test_storage.save_habits(
        [SingleSelectHabit(id="mood", name="Mood", options=["good", "bad"])]
    )

    client = TestClient(app)
    response = client.get("/calendar/mood?year=2025&month=1")

    assert "Legend" in response.text
    assert "good" in response.text
    assert "bad" in response.text


def test_calendar_no_legend_for_binary(test_storage):
    """Calendar does not show legend for binary habit."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    client = TestClient(app)
    response = client.get("/calendar/workout?year=2025&month=1")

    assert "Legend" not in response.text


# =============================================================================
# Habit Edit Form Tests (Phase 5)
# =============================================================================


def test_edit_habit_form_binary(test_storage):
    """GET /habits/{id}/edit shows edit form for binary habit."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    client = TestClient(app)
    response = client.get("/habits/workout/edit")

    assert response.status_code == 200
    assert "Workout" in response.text
    assert 'name="name"' in response.text
    assert 'name="color_yes"' in response.text
    assert 'name="color_no"' in response.text


def test_edit_habit_form_single_select(test_storage):
    """GET /habits/{id}/edit shows options for single-select habit."""
    test_storage.save_habits(
        [SingleSelectHabit(id="mood", name="Mood", options=["good", "bad"])]
    )

    client = TestClient(app)
    response = client.get("/habits/mood/edit")

    assert response.status_code == 200
    assert "good" in response.text
    assert "bad" in response.text
    assert "Add Option" in response.text


def test_edit_habit_form_numeric(test_storage):
    """GET /habits/{id}/edit shows unit and target for numeric habit."""
    test_storage.save_habits(
        [NumericHabit(id="water", name="Water", unit="glasses", target_value=8)]
    )

    client = TestClient(app)
    response = client.get("/habits/water/edit")

    assert response.status_code == 200
    assert "glasses" in response.text
    assert 'name="target_value"' in response.text
    assert 'name="unit"' in response.text


def test_edit_habit_not_found(test_storage):
    """GET /habits/{id}/edit returns 404 for unknown habit."""
    client = TestClient(app)
    response = client.get("/habits/nonexistent/edit")

    assert response.status_code == 404


def test_edit_habit_back_link_uses_correct_path(test_storage):
    """Back to Habits link navigates correctly from edit page."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    client = TestClient(app)
    response = client.get("/habits/workout/edit")

    assert response.status_code == 200
    # From /habits/workout/edit, we need "../.." to reach /habits
    # Should NOT contain "./habits" which would incorrectly go to /habits/workout/habits
    assert 'href="../.."' in response.text
    assert 'href="./habits"' not in response.text


def test_edit_habit_form_action_uses_correct_path(test_storage):
    """Edit form action targets correct endpoint."""
    test_storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    client = TestClient(app)
    response = client.get("/habits/workout/edit")

    assert response.status_code == 200
    # From /habits/workout/edit, the PUT endpoint /habits/workout is at ".."
    assert 'hx-put=".."' in response.text
    # Should NOT use ./habits/workout which would go to /habits/workout/habits/workout
    assert 'hx-put="./habits/' not in response.text
