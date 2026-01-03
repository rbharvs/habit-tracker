import os
from datetime import date, time

import boto3
import pytest
from moto import mock_aws

from habit_tracker.models import (
    BinaryEntry,
    BinaryHabit,
    DailyEntries,
    MultiSelectEntry,
    NumericEntry,
    NumericHabit,
    SingleSelectHabit,
    TimeEntry,
)
from habit_tracker.storage.dynamodb_storage import DynamoDBStorage


@pytest.fixture
def aws_credentials():
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def dynamodb_storage(aws_credentials):
    with mock_aws():
        # Create table
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-habits",
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield DynamoDBStorage(table_name="test-habits", region_name="us-east-1")


def test_load_habits_empty(dynamodb_storage):
    habits = dynamodb_storage.load_habits()
    assert habits == []


def test_save_and_load_habits(dynamodb_storage):
    habits = [
        BinaryHabit(id="workout", name="Work out?"),
        SingleSelectHabit(id="mood", name="Mood", options=["good", "bad"]),
    ]
    dynamodb_storage.save_habits(habits)
    loaded = dynamodb_storage.load_habits()

    assert len(loaded) == 2
    assert loaded[0].id == "workout"
    assert loaded[1].id == "mood"


def test_load_entries_not_found(dynamodb_storage):
    result = dynamodb_storage.load_entries(date(2025, 1, 1))
    assert result is None


def test_save_and_load_entries(dynamodb_storage):
    day = date(2025, 12, 26)
    entries = DailyEntries(
        date=day,
        entries={"workout": BinaryEntry(value=True)},
    )
    dynamodb_storage.save_entries(entries)
    loaded = dynamodb_storage.load_entries(day)

    assert loaded is not None
    assert loaded.date == day
    assert loaded.entries["workout"].value is True


def test_save_and_load_numeric_entry(dynamodb_storage):
    """NumericEntry roundtrips through DynamoDB correctly."""
    day = date(2025, 1, 5)
    entries = DailyEntries(
        date=day,
        entries={"water": NumericEntry(value=8)},
    )
    dynamodb_storage.save_entries(entries)
    loaded = dynamodb_storage.load_entries(day)

    assert loaded is not None
    assert loaded.entries["water"].value == 8


def test_save_and_load_time_entry(dynamodb_storage):
    """TimeEntry roundtrips through DynamoDB correctly."""
    day = date(2025, 1, 5)
    entries = DailyEntries(
        date=day,
        entries={"bedtime": TimeEntry(value=time(22, 30))},
    )
    dynamodb_storage.save_entries(entries)
    loaded = dynamodb_storage.load_entries(day)

    assert loaded is not None
    assert loaded.entries["bedtime"].value == time(22, 30)


def test_save_and_load_multi_select_entry(dynamodb_storage):
    """MultiSelectEntry roundtrips through DynamoDB correctly."""
    day = date(2025, 1, 5)
    entries = DailyEntries(
        date=day,
        entries={"exercises": MultiSelectEntry(value=["cardio", "strength"])},
    )
    dynamodb_storage.save_entries(entries)
    loaded = dynamodb_storage.load_entries(day)

    assert loaded is not None
    assert loaded.entries["exercises"].value == ["cardio", "strength"]


def test_habit_order_preserved_after_reorder(dynamodb_storage):
    """Habit order is preserved through save/load with sort_order."""
    habits = [
        BinaryHabit(id="habit1", name="Habit 1"),
        BinaryHabit(id="habit2", name="Habit 2"),
        BinaryHabit(id="habit3", name="Habit 3"),
    ]
    dynamodb_storage.save_habits(habits)

    # Reorder: swap habit1 and habit2
    reordered = [habits[1], habits[0], habits[2]]
    dynamodb_storage.save_habits(reordered)

    loaded = dynamodb_storage.load_habits()
    assert [h.id for h in loaded] == ["habit2", "habit1", "habit3"]


# =============================================================================
# Integration Tests: Move Endpoints with DynamoDB
# =============================================================================


@pytest.fixture
def dynamodb_client(aws_credentials):
    """Create DynamoDB storage and override app dependency."""
    from fastapi.testclient import TestClient

    from habit_tracker.main import app
    from habit_tracker.storage import get_storage

    with mock_aws():
        # Create table
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="test-habits",
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        storage = DynamoDBStorage(table_name="test-habits", region_name="us-east-1")
        app.dependency_overrides[get_storage] = lambda: storage
        yield TestClient(app), storage
        app.dependency_overrides.clear()


def test_move_habit_up_dynamodb(dynamodb_client):
    """Test moving a habit up via API with DynamoDB storage."""
    client, storage = dynamodb_client
    storage.save_habits(
        [
            BinaryHabit(id="habit1", name="Habit 1"),
            BinaryHabit(id="habit2", name="Habit 2"),
            BinaryHabit(id="habit3", name="Habit 3"),
        ]
    )

    response = client.post("/habits/habit2/move-up", follow_redirects=False)
    assert response.status_code == 303

    habits = storage.load_habits()
    assert [h.id for h in habits] == ["habit2", "habit1", "habit3"]


def test_move_habit_down_dynamodb(dynamodb_client):
    """Test moving a habit down via API with DynamoDB storage."""
    client, storage = dynamodb_client
    storage.save_habits(
        [
            BinaryHabit(id="habit1", name="Habit 1"),
            BinaryHabit(id="habit2", name="Habit 2"),
            BinaryHabit(id="habit3", name="Habit 3"),
        ]
    )

    response = client.post("/habits/habit1/move-down", follow_redirects=False)
    assert response.status_code == 303

    habits = storage.load_habits()
    assert [h.id for h in habits] == ["habit2", "habit1", "habit3"]


def test_move_habit_order_persists_dynamodb(dynamodb_client):
    """Verify reordered habits persist after multiple operations with DynamoDB."""
    client, storage = dynamodb_client
    storage.save_habits(
        [
            BinaryHabit(id="a", name="A"),
            BinaryHabit(id="b", name="B"),
            BinaryHabit(id="c", name="C"),
        ]
    )

    # Move C to top: C up, C up
    client.post("/habits/c/move-up", follow_redirects=False)
    client.post("/habits/c/move-up", follow_redirects=False)

    habits = storage.load_habits()
    assert [h.id for h in habits] == ["c", "a", "b"]

    # Verify order shows correctly on index page
    response = client.get("/")
    assert response.status_code == 200
    a_pos = response.text.find("A")
    b_pos = response.text.find("B")
    c_pos = response.text.find("C")
    assert c_pos < a_pos < b_pos


def test_archived_habit_skipped_dynamodb(dynamodb_client):
    """Moving skips archived habits with DynamoDB storage."""
    client, storage = dynamodb_client
    storage.save_habits(
        [
            BinaryHabit(id="habit1", name="Habit 1"),
            BinaryHabit(id="habit2", name="Habit 2", archived=True),
            BinaryHabit(id="habit3", name="Habit 3"),
        ]
    )

    # Move habit3 up should skip archived habit2 and swap with habit1
    response = client.post("/habits/habit3/move-up", follow_redirects=False)
    assert response.status_code == 303

    habits = storage.load_habits()
    assert [h.id for h in habits] == ["habit3", "habit2", "habit1"]


def test_save_and_load_habits_with_colors(dynamodb_storage):
    """Habits with color fields roundtrip through DynamoDB."""
    habits = [
        BinaryHabit(
            id="workout", name="Workout", color_yes="#00ff00", color_no="#ff0000"
        ),
        NumericHabit(id="water", name="Water", color_target="#3b82f6", target_value=8),
    ]
    dynamodb_storage.save_habits(habits)
    loaded = dynamodb_storage.load_habits()

    assert loaded[0].color_yes == "#00ff00"
    assert loaded[1].color_target == "#3b82f6"
    assert loaded[1].target_value == 8


def test_load_entries_range_dynamodb(dynamodb_storage):
    """load_entries_range returns entries within date range from DynamoDB."""
    # Create entries for 5 consecutive days
    for i in range(5):
        day = date(2025, 1, 10 + i)
        dynamodb_storage.save_entries(
            DailyEntries(date=day, entries={"test": BinaryEntry(value=True)})
        )

    # Query middle 3 days
    result = dynamodb_storage.load_entries_range(date(2025, 1, 11), date(2025, 1, 13))

    assert len(result) == 3
    assert date(2025, 1, 11) in result
    assert date(2025, 1, 12) in result
    assert date(2025, 1, 13) in result


def test_load_entries_range_empty_dynamodb(dynamodb_storage):
    """load_entries_range returns empty dict when no entries in DynamoDB."""
    result = dynamodb_storage.load_entries_range(date(2025, 1, 1), date(2025, 1, 31))
    assert result == {}


def test_update_habit_dynamodb(dynamodb_client):
    """PUT /habits/{id} persists to DynamoDB."""
    client, storage = dynamodb_client
    storage.save_habits([BinaryHabit(id="workout", name="Workout")])

    response = client.put(
        "/habits/workout",
        data={"name": "Morning Workout", "color_yes": "#00ff00", "color_no": "#ff0000"},
        follow_redirects=False,
    )

    assert response.status_code == 303

    habits = storage.load_habits()
    assert habits[0].name == "Morning Workout"
    assert habits[0].color_yes == "#00ff00"
