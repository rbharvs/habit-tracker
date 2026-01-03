from pathlib import Path

import pytest
import time_machine
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode

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


# Custom HTML snapshot extension for readable .html files
class HTMLSnapshotExtension(SingleFileSnapshotExtension):
    _write_mode = WriteMode.TEXT
    _file_extension = "html"
    file_extension = "html"  # Override parent class attribute for actual file extension


@pytest.fixture
def snapshot_html(snapshot):
    """Snapshot fixture that stores HTML as .html files."""
    return snapshot.use_extension(HTMLSnapshotExtension)


@pytest.fixture
def frozen_time():
    """Freeze time to a deterministic value for snapshot tests."""
    with time_machine.travel("2025-01-15 10:30:00", tick=False) as t:
        yield t


@pytest.fixture
def deterministic(frozen_time, test_storage):
    """Combined fixture for fully deterministic snapshot tests."""
    pass


@pytest.fixture
def client():
    """TestClient fixture for consistent usage across tests."""
    from starlette.testclient import TestClient

    from habit_tracker.main import app

    return TestClient(app)
