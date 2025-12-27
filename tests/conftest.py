from pathlib import Path

import pytest

from habit_tracker.storage import get_storage
from habit_tracker.storage.json_storage import JsonFileStorage


@pytest.fixture(autouse=True)
def test_storage(tmp_path: Path):
    """Override storage with temporary directory."""
    from habit_tracker.main import app

    test_storage = JsonFileStorage(data_dir=tmp_path / "data")
    app.dependency_overrides[get_storage] = lambda: test_storage
    yield test_storage
    app.dependency_overrides.clear()
