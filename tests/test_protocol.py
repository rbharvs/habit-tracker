"""Tests for StorageProtocol - verify the protocol contract."""

from datetime import date


def test_storage_protocol_exists():
    """StorageProtocol should be importable from habit_tracker.storage."""
    from habit_tracker.storage import StorageProtocol

    # Protocol should define expected methods
    assert hasattr(StorageProtocol, "load_habits")
    assert hasattr(StorageProtocol, "save_habits")
    assert hasattr(StorageProtocol, "load_entries")
    assert hasattr(StorageProtocol, "save_entries")


def test_json_file_storage_implements_protocol():
    """JsonFileStorage should implement StorageProtocol."""

    import tempfile

    # JsonFileStorage should be a structural subtype of StorageProtocol
    # We can check this by creating an instance and using it where
    # StorageProtocol is expected
    from pathlib import Path

    from habit_tracker.storage.json_storage import JsonFileStorage

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JsonFileStorage(data_dir=Path(tmpdir))
        # If this doesn't raise, the protocol is implemented
        _verify_protocol(storage)


def _verify_protocol(storage):
    """Helper to verify storage implements protocol methods."""
    from habit_tracker.models import BinaryEntry, BinaryHabit, DailyEntries

    # Test load_habits returns list
    habits = storage.load_habits()
    assert isinstance(habits, list)

    # Test save_habits
    storage.save_habits([BinaryHabit(id="test", name="Test")])

    # Test load_entries returns None or DailyEntries
    result = storage.load_entries(date(2025, 1, 1))
    assert result is None or hasattr(result, "entries")

    # Test save_entries
    storage.save_entries(
        DailyEntries(date=date(2025, 1, 1), entries={"test": BinaryEntry(value=True)})
    )
