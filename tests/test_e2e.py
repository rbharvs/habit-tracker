"""End-to-end test using TestClient for full request/response cycle."""

import shutil
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from habit_tracker import storage
from habit_tracker.main import app
from habit_tracker.models import BinaryHabit


def setup_test_storage():
    """Use a test data directory."""
    test_dir = Path("test_data")
    storage.DATA_DIR = test_dir
    storage.CONFIG_FILE = test_dir / "config.json"
    storage.ENTRIES_DIR = test_dir / "entries"
    storage.ensure_dirs()
    return test_dir


def cleanup_test_storage(test_dir: Path):
    """Clean up test data directory."""
    shutil.rmtree(test_dir, ignore_errors=True)


def test_save_and_load_entries():
    """Full e2e: save entries via form POST, verify persistence."""
    test_dir = setup_test_storage()
    try:
        # Setup: create a test habit
        habits = [BinaryHabit(id="test", name="Test")]
        storage.save_habits(habits)

        client = TestClient(app)
        # Submit form with checkbox checked
        response = client.post(
            "/save",
            data={"date": date.today().isoformat(), "habit_test": "on"},
            follow_redirects=False,
        )
        assert response.status_code == 303

        # Verify entry was saved
        entries = storage.load_entries(date.today())
        assert entries is not None
        assert entries.entries["test"].value is True
    finally:
        cleanup_test_storage(test_dir)
