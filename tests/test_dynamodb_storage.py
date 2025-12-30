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
