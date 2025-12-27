"""Tests for FastAPI routes (main.py)."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from habit_tracker.main import app
from habit_tracker.models import (
    BinaryEntry,
    BinaryHabit,
    DailyEntries,
    JournalHabit,
    SingleSelectHabit,
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


def test_today_hides_next_link(test_storage):
    """When viewing today, next link is not shown."""
    client = TestClient(app)
    today = date.today()
    tomorrow = today + timedelta(days=1)
    response = client.get(f"/?day={today.isoformat()}")
    # Should not show tomorrow's date link
    assert f"day={tomorrow.isoformat()}" not in response.text


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
