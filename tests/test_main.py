"""Tests for FastAPI routes (main.py)."""

import shutil
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient


def setup_test_storage():
    """Use a test data directory."""
    from habit_tracker import storage

    test_dir = Path("test_data")
    storage.DATA_DIR = test_dir
    storage.CONFIG_FILE = test_dir / "config.json"
    storage.ENTRIES_DIR = test_dir / "entries"
    storage.ensure_dirs()
    return test_dir


def cleanup_test_storage(test_dir: Path):
    """Clean up test data directory."""
    shutil.rmtree(test_dir, ignore_errors=True)


def test_index_returns_html():
    """GET / returns HTML response."""
    test_dir = setup_test_storage()
    try:
        from habit_tracker.main import app

        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
    finally:
        cleanup_test_storage(test_dir)


def test_index_shows_today_by_default():
    """GET / without day param shows today's date."""
    test_dir = setup_test_storage()
    try:
        from habit_tracker.main import app

        client = TestClient(app)
        response = client.get("/")
        today = date.today()
        assert today.strftime("%b %d") in response.text
    finally:
        cleanup_test_storage(test_dir)


def test_index_accepts_day_param():
    """GET /?day=2025-01-05 shows that date."""
    test_dir = setup_test_storage()
    try:
        from habit_tracker.main import app

        client = TestClient(app)
        response = client.get("/?day=2025-01-05")
        assert response.status_code == 200
        assert "Jan 05" in response.text
    finally:
        cleanup_test_storage(test_dir)


def test_index_shows_habits():
    """GET / shows configured habits."""
    test_dir = setup_test_storage()
    try:
        from habit_tracker import storage
        from habit_tracker.main import app
        from habit_tracker.models import BinaryHabit

        storage.save_habits([BinaryHabit(id="workout", name="Did you work out?")])

        client = TestClient(app)
        response = client.get("/")
        assert "Did you work out?" in response.text
    finally:
        cleanup_test_storage(test_dir)


def test_index_shows_empty_form_when_no_habits():
    """GET / shows empty form when no habits configured."""
    test_dir = setup_test_storage()
    try:
        from habit_tracker.main import app

        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        # Form should still exist even with no habits
        assert "<form" in response.text
    finally:
        cleanup_test_storage(test_dir)


def test_save_creates_entry():
    """POST /save creates entry for date."""
    test_dir = setup_test_storage()
    try:
        from habit_tracker import storage
        from habit_tracker.main import app
        from habit_tracker.models import BinaryHabit

        storage.save_habits([BinaryHabit(id="test", name="Test")])

        client = TestClient(app)
        response = client.post(
            "/save",
            data={"date": "2025-01-05", "habit_test": "on"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "day=2025-01-05" in response.headers["location"]

        entries = storage.load_entries(date(2025, 1, 5))
        assert entries is not None
        assert entries.entries["test"].value is True
    finally:
        cleanup_test_storage(test_dir)


def test_save_binary_unchecked():
    """POST /save without checkbox creates false entry."""
    test_dir = setup_test_storage()
    try:
        from habit_tracker import storage
        from habit_tracker.main import app
        from habit_tracker.models import BinaryHabit

        storage.save_habits([BinaryHabit(id="test", name="Test")])

        client = TestClient(app)
        client.post("/save", data={"date": "2025-01-05"}, follow_redirects=False)

        entries = storage.load_entries(date(2025, 1, 5))
        assert entries.entries["test"].value is False
    finally:
        cleanup_test_storage(test_dir)


def test_save_single_select():
    """POST /save with radio selection creates single select entry."""
    test_dir = setup_test_storage()
    try:
        from habit_tracker import storage
        from habit_tracker.main import app
        from habit_tracker.models import SingleSelectHabit

        storage.save_habits(
            [SingleSelectHabit(id="mood", name="Mood", options=["good", "bad"])]
        )

        client = TestClient(app)
        client.post(
            "/save",
            data={"date": "2025-01-05", "habit_mood": "good"},
            follow_redirects=False,
        )

        entries = storage.load_entries(date(2025, 1, 5))
        assert entries.entries["mood"].value == "good"
    finally:
        cleanup_test_storage(test_dir)


def test_save_journal():
    """POST /save with textarea creates journal entry."""
    test_dir = setup_test_storage()
    try:
        from habit_tracker import storage
        from habit_tracker.main import app
        from habit_tracker.models import JournalHabit

        storage.save_habits([JournalHabit(id="notes", name="Notes")])

        client = TestClient(app)
        client.post(
            "/save",
            data={"date": "2025-01-05", "habit_notes": "Great day!"},
            follow_redirects=False,
        )

        entries = storage.load_entries(date(2025, 1, 5))
        assert entries.entries["notes"].value == "Great day!"
    finally:
        cleanup_test_storage(test_dir)


def test_index_shows_existing_entries():
    """GET / shows previously saved entries."""
    test_dir = setup_test_storage()
    try:
        from habit_tracker import storage
        from habit_tracker.main import app
        from habit_tracker.models import BinaryEntry, BinaryHabit, DailyEntries

        storage.save_habits([BinaryHabit(id="test", name="Test")])
        storage.save_entries(
            DailyEntries(date=date.today(), entries={"test": BinaryEntry(value=True)})
        )

        client = TestClient(app)
        response = client.get("/")
        # Checkbox should be checked
        assert "checked" in response.text
    finally:
        cleanup_test_storage(test_dir)


def test_date_navigation_links():
    """Index page has prev/next date navigation links."""
    test_dir = setup_test_storage()
    try:
        from habit_tracker.main import app

        client = TestClient(app)
        response = client.get("/?day=2025-01-05")
        assert "day=2025-01-04" in response.text  # prev
        assert "day=2025-01-06" in response.text  # next
    finally:
        cleanup_test_storage(test_dir)


def test_today_hides_next_link():
    """When viewing today, next link is not shown."""
    test_dir = setup_test_storage()
    try:
        from habit_tracker.main import app

        client = TestClient(app)
        today = date.today()
        tomorrow = today + timedelta(days=1)
        response = client.get(f"/?day={today.isoformat()}")
        # Should not show tomorrow's date link
        assert f"day={tomorrow.isoformat()}" not in response.text
    finally:
        cleanup_test_storage(test_dir)


def test_save_htmx_returns_indicator():
    """POST /save with HX-Request header returns saved indicator instead of redirect."""
    test_dir = setup_test_storage()
    try:
        from habit_tracker import storage
        from habit_tracker.main import app
        from habit_tracker.models import BinaryHabit

        storage.save_habits([BinaryHabit(id="test", name="Test")])

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
    finally:
        cleanup_test_storage(test_dir)


def test_save_htmx_indicator_has_timestamp_tooltip():
    """POST /save with HX-Request header includes timestamp in title attribute."""
    test_dir = setup_test_storage()
    try:
        from habit_tracker import storage
        from habit_tracker.main import app
        from habit_tracker.models import BinaryHabit

        storage.save_habits([BinaryHabit(id="test", name="Test")])

        client = TestClient(app)
        response = client.post(
            "/save",
            data={"date": "2025-01-05", "habit_test": "on"},
            headers={"HX-Request": "true"},
        )
        # Should have a title attribute with timestamp for mouseover
        assert 'title="Saved at' in response.text
    finally:
        cleanup_test_storage(test_dir)


def test_save_htmx_still_persists_data():
    """POST /save with HX-Request header still saves data."""
    test_dir = setup_test_storage()
    try:
        from habit_tracker import storage
        from habit_tracker.main import app
        from habit_tracker.models import BinaryHabit

        storage.save_habits([BinaryHabit(id="test", name="Test")])

        client = TestClient(app)
        client.post(
            "/save",
            data={"date": "2025-01-05", "habit_test": "on"},
            headers={"HX-Request": "true"},
        )

        # Verify data was saved
        entries = storage.load_entries(date(2025, 1, 5))
        assert entries is not None
        assert entries.entries["test"].value is True
    finally:
        cleanup_test_storage(test_dir)


def test_index_has_mobile_meta_tags():
    """GET / includes mobile-friendly meta tags."""
    test_dir = setup_test_storage()
    try:
        from habit_tracker.main import app

        client = TestClient(app)
        response = client.get("/")
        # Check for PWA-friendly meta tags
        assert 'name="apple-mobile-web-app-capable"' in response.text
        assert 'name="theme-color"' in response.text
    finally:
        cleanup_test_storage(test_dir)


def test_index_has_save_button():
    """GET / has a save button that works on mobile."""
    test_dir = setup_test_storage()
    try:
        from habit_tracker.main import app

        client = TestClient(app)
        response = client.get("/")
        assert '<button type="submit"' in response.text
        assert "Save" in response.text
    finally:
        cleanup_test_storage(test_dir)
