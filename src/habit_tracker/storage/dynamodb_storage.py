from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from pydantic import TypeAdapter

from habit_tracker.models import DailyEntries, Habit


def _to_dynamodb(obj: Any) -> Any:
    """Convert floats to Decimal for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _to_dynamodb(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_dynamodb(v) for v in obj]
    return obj


def _from_dynamodb(obj: Any) -> Any:
    """Convert Decimals back to float."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _from_dynamodb(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_from_dynamodb(v) for v in obj]
    return obj


@dataclass
class DynamoDBStorage:
    """DynamoDB storage using single-table design.

    Schema (from docs/research/2025-12-27-dynamodb-single-table-design.md):
    - Habits: pk=USER#default, sk=HABIT#<habit_id>
    - Entries: pk=USER#default, sk=ENTRY#<date>
    """

    table_name: str
    region_name: str = "us-east-1"
    endpoint_url: str | None = None
    _table: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        kwargs: dict[str, Any] = {"region_name": self.region_name}
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        dynamodb = boto3.resource("dynamodb", **kwargs)
        self._table = dynamodb.Table(self.table_name)

    def _user_pk(self) -> str:
        return "USER#default"  # Hardcoded for single-user

    def load_habits(self) -> list[Habit]:
        response = self._table.query(
            KeyConditionExpression=Key("pk").eq(self._user_pk())
            & Key("sk").begins_with("HABIT#")
        )
        items = response.get("Items", [])
        # Sort by sort_order if present, then by id
        items.sort(key=lambda x: (x.get("sort_order", 999), x.get("id", "")))
        adapter = TypeAdapter(list[Habit])
        return adapter.validate_python([_from_dynamodb(item) for item in items])

    def save_habits(self, habits: list[Habit]) -> None:
        # Delete existing habits
        response = self._table.query(
            KeyConditionExpression=Key("pk").eq(self._user_pk())
            & Key("sk").begins_with("HABIT#"),
            ProjectionExpression="pk, sk",
        )
        with self._table.batch_writer() as batch:
            for item in response.get("Items", []):
                batch.delete_item(Key={"pk": item["pk"], "sk": item["sk"]})

        # Write new habits
        with self._table.batch_writer() as batch:
            for i, habit in enumerate(habits):
                item = _to_dynamodb(habit.model_dump())
                item["pk"] = self._user_pk()
                item["sk"] = f"HABIT#{habit.id}"
                item["sort_order"] = i
                batch.put_item(Item=item)

    def load_entries(self, day: date) -> DailyEntries | None:
        response = self._table.get_item(
            Key={"pk": self._user_pk(), "sk": f"ENTRY#{day.isoformat()}"}
        )
        item = response.get("Item")
        if not item:
            return None
        return DailyEntries(
            date=day,
            entries=_from_dynamodb(item.get("entries", {})),
        )

    def save_entries(self, entries: DailyEntries) -> None:
        self._table.put_item(
            Item={
                "pk": self._user_pk(),
                "sk": f"ENTRY#{entries.date.isoformat()}",
                "date": entries.date.isoformat(),
                "entries": _to_dynamodb(
                    {k: v.model_dump(mode="json") for k, v in entries.entries.items()}
                ),
            }
        )
