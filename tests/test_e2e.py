"""End-to-end test using TestClient for full request/response cycle."""

from datetime import date

from fastapi.testclient import TestClient

from habit_tracker.main import app
from habit_tracker.models import BinaryHabit


def test_save_and_load_entries(test_storage):
    """Full e2e: save entries via form POST, verify persistence."""
    # Setup: create a test habit
    habits = [BinaryHabit(id="test", name="Test")]
    test_storage.save_habits(habits)

    client = TestClient(app)
    # Submit form with checkbox checked
    response = client.post(
        "/save",
        data={"date": date.today().isoformat(), "habit_test": "on"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    # Verify entry was saved
    entries = test_storage.load_entries(date.today())
    assert entries is not None
    assert entries.entries["test"].value is True
