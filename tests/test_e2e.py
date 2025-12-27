"""End-to-end test using httpx for full request/response cycle."""

import shutil
from datetime import date
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from habit_tracker import storage
from habit_tracker.main import app
from habit_tracker.models import BinaryHabit


@pytest.fixture(autouse=True)
def clean_data():
    """Use a test data directory."""
    test_dir = Path("test_data")
    storage.DATA_DIR = test_dir
    storage.CONFIG_FILE = test_dir / "config.json"
    storage.ENTRIES_DIR = test_dir / "entries"
    storage.ensure_dirs()
    yield
    shutil.rmtree(test_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_save_and_load_entries():
    """Full e2e: save entries via form POST, verify persistence."""
    # Setup: create a test habit
    habits = [BinaryHabit(id="test", name="Test")]
    storage.save_habits(habits)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Submit form with checkbox checked
        response = await client.post(
            "/save",
            data={"date": date.today().isoformat(), "habit_test": "on"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        # Verify entry was saved
        entries = storage.load_entries(date.today())
        assert entries is not None
        assert entries.entries["test"].value is True
