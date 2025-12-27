"""Tests for FastAPI routes (main.py)."""

import shutil
from datetime import date, timedelta
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def clean_test_data():
    """Use a test data directory and clean up after each test."""
    from habit_tracker import storage

    test_dir = Path("test_data")
    storage.DATA_DIR = test_dir
    storage.CONFIG_FILE = test_dir / "config.json"
    storage.ENTRIES_DIR = test_dir / "entries"
    storage.ensure_dirs()
    yield
    shutil.rmtree(test_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_index_returns_html():
    """GET / returns HTML response."""
    from habit_tracker.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_index_shows_today_by_default():
    """GET / without day param shows today's date."""
    from habit_tracker.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")
        today = date.today()
        assert today.strftime("%b %d") in response.text


@pytest.mark.asyncio
async def test_index_accepts_day_param():
    """GET /?day=2025-01-05 shows that date."""
    from habit_tracker.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/?day=2025-01-05")
        assert response.status_code == 200
        assert "Jan 05" in response.text


@pytest.mark.asyncio
async def test_index_shows_habits():
    """GET / shows configured habits."""
    from habit_tracker import storage
    from habit_tracker.main import app
    from habit_tracker.models import BinaryHabit

    storage.save_habits([BinaryHabit(id="workout", name="Did you work out?")])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")
        assert "Did you work out?" in response.text


@pytest.mark.asyncio
async def test_index_shows_empty_form_when_no_habits():
    """GET / shows empty form when no habits configured."""
    from habit_tracker.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")
        assert response.status_code == 200
        # Form should still exist even with no habits
        assert "<form" in response.text


@pytest.mark.asyncio
async def test_save_creates_entry():
    """POST /save creates entry for date."""
    from habit_tracker import storage
    from habit_tracker.main import app
    from habit_tracker.models import BinaryHabit

    storage.save_habits([BinaryHabit(id="test", name="Test")])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/save",
            data={"date": "2025-01-05", "habit_test": "on"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "day=2025-01-05" in response.headers["location"]

    entries = storage.load_entries(date(2025, 1, 5))
    assert entries is not None
    assert entries.entries["test"].value is True


@pytest.mark.asyncio
async def test_save_binary_unchecked():
    """POST /save without checkbox creates false entry."""
    from habit_tracker import storage
    from habit_tracker.main import app
    from habit_tracker.models import BinaryHabit

    storage.save_habits([BinaryHabit(id="test", name="Test")])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post("/save", data={"date": "2025-01-05"}, follow_redirects=False)

    entries = storage.load_entries(date(2025, 1, 5))
    assert entries.entries["test"].value is False


@pytest.mark.asyncio
async def test_save_single_select():
    """POST /save with radio selection creates single select entry."""
    from habit_tracker import storage
    from habit_tracker.main import app
    from habit_tracker.models import SingleSelectHabit

    storage.save_habits(
        [SingleSelectHabit(id="mood", name="Mood", options=["good", "bad"])]
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            "/save",
            data={"date": "2025-01-05", "habit_mood": "good"},
            follow_redirects=False,
        )

    entries = storage.load_entries(date(2025, 1, 5))
    assert entries.entries["mood"].value == "good"


@pytest.mark.asyncio
async def test_save_journal():
    """POST /save with textarea creates journal entry."""
    from habit_tracker import storage
    from habit_tracker.main import app
    from habit_tracker.models import JournalHabit

    storage.save_habits([JournalHabit(id="notes", name="Notes")])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            "/save",
            data={"date": "2025-01-05", "habit_notes": "Great day!"},
            follow_redirects=False,
        )

    entries = storage.load_entries(date(2025, 1, 5))
    assert entries.entries["notes"].value == "Great day!"


@pytest.mark.asyncio
async def test_index_shows_existing_entries():
    """GET / shows previously saved entries."""
    from habit_tracker import storage
    from habit_tracker.main import app
    from habit_tracker.models import BinaryEntry, BinaryHabit, DailyEntries

    storage.save_habits([BinaryHabit(id="test", name="Test")])
    storage.save_entries(
        DailyEntries(date=date.today(), entries={"test": BinaryEntry(value=True)})
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")
        # Checkbox should be checked
        assert "checked" in response.text


@pytest.mark.asyncio
async def test_date_navigation_links():
    """Index page has prev/next date navigation links."""
    from habit_tracker.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/?day=2025-01-05")
        assert "day=2025-01-04" in response.text  # prev
        assert "day=2025-01-06" in response.text  # next


@pytest.mark.asyncio
async def test_today_hides_next_link():
    """When viewing today, next link is not shown."""
    from habit_tracker.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        today = date.today()
        tomorrow = today + timedelta(days=1)
        response = await client.get(f"/?day={today.isoformat()}")
        # Should not show tomorrow's date link
        assert f"day={tomorrow.isoformat()}" not in response.text
