# Research: DynamoDB Single Table Design for Habit Tracker

**Date**: 2025-12-27T02:37:46Z
**Git Commit**: 8da29ab8fa92e0ab82e6d2eda59d77fff5eed152
**Branch**: main

## Research Question

How should we structure a DynamoDB single table for the habit-tracker application, given:
1. We're planning to host on Lambda + DynamoDB (per hosting-options research)
2. Habit configuration will soon be API-manageable (not just fixed config)
3. We may eventually support multiple users (but start with single hardcoded user)

## Summary

A single-table design with composite keys (`pk` + `sk`) using entity-type prefixes provides the flexibility needed for habit tracking while allowing future multi-user expansion. The recommended schema uses:

- **`pk`**: Entity scope (user, or global for shared data)
- **`sk`**: Entity type + identifier (e.g., `HABIT#workout`, `ENTRY#2025-01-15#workout`)

This design supports all current access patterns with single-item operations, enables multi-user isolation via partition key prefixes, and requires no GSIs for the current feature set.

## Current Access Patterns

Based on analysis of `src/habit_tracker/main.py` and `src/habit_tracker/storage.py`:

| Operation | Current Implementation | Frequency |
|-----------|----------------------|-----------|
| Load all habits | `load_habits()` → reads `config.json` | Every page load |
| Load entries for a day | `load_entries(date)` → reads `YYYY-MM-DD.json` | Every page load |
| Save all entries for a day | `save_entries(DailyEntries)` → writes `YYYY-MM-DD.json` | Every form save (auto-save) |
| Save habits (future) | `save_habits(habits)` → writes `config.json` | Rare (config changes) |

### Future Access Patterns (Anticipated)

| Operation | Use Case |
|-----------|----------|
| Get single habit by ID | Edit habit configuration |
| List habits for a user | Multi-user support |
| Get entries for date range | History/analytics view |
| Get entries for specific habit | Habit-specific history |

## Existing Data Model

From `src/habit_tracker/models.py`:

```python
# Habit types (discriminated union)
Habit = BinaryHabit | SingleSelectHabit | JournalHabit
# Fields: type, id, name, (options for SingleSelect)

# Entry types (discriminated union)
HabitEntry = BinaryEntry | SingleSelectEntry | JournalEntry
# Fields: type, value

# Daily container
DailyEntries = { date: date, entries: dict[habit_id, HabitEntry] }
```

## Proposed DynamoDB Schema

### Table Definition

```yaml
TableName: habit-tracker
BillingMode: PAY_PER_REQUEST
KeySchema:
  - AttributeName: pk
    KeyType: HASH
  - AttributeName: sk
    KeyType: RANGE
AttributeDefinitions:
  - AttributeName: pk
    AttributeType: S
  - AttributeName: sk
    AttributeType: S
```

### Entity Key Patterns

| Entity | pk | sk | Example |
|--------|----|----|---------|
| **Habit Definition** | `USER#<user_id>` | `HABIT#<habit_id>` | `pk=USER#default`, `sk=HABIT#workout` |
| **Daily Entries** | `USER#<user_id>` | `ENTRY#<date>` | `pk=USER#default`, `sk=ENTRY#2025-01-15` |

### Item Structures

#### Habit Item
```json
{
  "pk": "USER#default",
  "sk": "HABIT#workout",
  "type": "binary",
  "id": "workout",
  "name": "Did you work out?",
  "created_at": "2025-01-01T00:00:00Z",
  "sort_order": 1
}
```

#### Single-Select Habit Item
```json
{
  "pk": "USER#default",
  "sk": "HABIT#mood",
  "type": "single_select",
  "id": "mood",
  "name": "How was your mood?",
  "options": ["great", "good", "okay", "bad"],
  "created_at": "2025-01-01T00:00:00Z",
  "sort_order": 2
}
```

#### Daily Entries Item
```json
{
  "pk": "USER#default",
  "sk": "ENTRY#2025-01-15",
  "date": "2025-01-15",
  "entries": {
    "workout": {"type": "binary", "value": true},
    "mood": {"type": "single_select", "value": "good"},
    "journal": {"type": "journal", "value": "Had a productive day..."}
  },
  "updated_at": "2025-01-15T22:30:00Z"
}
```

### Access Pattern Implementation

| Access Pattern | DynamoDB Operation | Key Condition |
|----------------|-------------------|---------------|
| Load all habits for user | `Query` | `pk = USER#<user_id> AND begins_with(sk, "HABIT#")` |
| Load entries for a day | `GetItem` | `pk = USER#<user_id>, sk = ENTRY#<date>` |
| Save entries for a day | `PutItem` | `pk = USER#<user_id>, sk = ENTRY#<date>` |
| Get single habit | `GetItem` | `pk = USER#<user_id>, sk = HABIT#<habit_id>` |
| Get entries for date range | `Query` | `pk = USER#<user_id> AND sk BETWEEN ENTRY#<start> AND ENTRY#<end>` |

## Design Decisions

### Why Store Entries as Single Item Per Day (Not Per Habit)

The current application saves all habit entries for a day atomically in one form submission. Storing as a single item per day:

1. **Matches the access pattern**: Always load/save all entries for a day together
2. **Reduces WCU costs**: One write per save vs. N writes (one per habit)
3. **Simplifies consistency**: No partial-day states possible
4. **Enables atomic updates**: Single `PutItem` replaces all entries

Trade-off: Cannot query "all entries for habit X across dates" without scanning. If this becomes needed, add a GSI with `pk=USER#<user_id>#HABIT#<habit_id>`, `sk=<date>`.

### Why Not Store Habits as Single Config Item

The hosting-options document showed a simpler design storing all habits in one item. However, storing habits individually allows:

1. **Individual habit CRUD**: Add/update/delete habits without read-modify-write
2. **Concurrent updates**: Multiple habit edits don't conflict
3. **Sort order flexibility**: Can add `sort_order` attribute for ordering

Trade-off: Requires `Query` instead of `GetItem` to fetch all habits (~same latency for small item counts).

### User ID Strategy

Using `USER#default` as the initial user ID:

1. **Trivial migration to multi-user**: Just change the user ID extraction logic
2. **IAM-compatible**: Partition key prefix enables row-level security via `dynamodb:LeadingKeys` condition
3. **No schema changes needed**: Multi-user works without table modifications

### Why No GSIs (Yet)

Current access patterns are all satisfied by the base table:
- All queries scope to a single user (partition)
- Date range queries work via sort key conditions
- No cross-user aggregations needed

Add GSIs only when new access patterns require them (e.g., admin dashboards, cross-user analytics).

## Storage Layer Changes

The current `storage.py` would be replaced with:

```python
# Conceptual implementation (not production-ready)
import os
import boto3
from datetime import date
from habit_tracker.models import Habit, DailyEntries

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("TABLE_NAME", "habit-tracker"))

USER_ID = "default"  # Hardcoded for now

def load_habits() -> list[Habit]:
    response = table.query(
        KeyConditionExpression="pk = :pk AND begins_with(sk, :prefix)",
        ExpressionAttributeValues={
            ":pk": f"USER#{USER_ID}",
            ":prefix": "HABIT#"
        }
    )
    return [parse_habit(item) for item in response.get("Items", [])]

def save_habit(habit: Habit) -> None:
    table.put_item(Item={
        "pk": f"USER#{USER_ID}",
        "sk": f"HABIT#{habit.id}",
        **habit.model_dump()
    })

def load_entries(day: date) -> DailyEntries | None:
    response = table.get_item(
        Key={"pk": f"USER#{USER_ID}", "sk": f"ENTRY#{day.isoformat()}"}
    )
    if "Item" not in response:
        return None
    return DailyEntries(**response["Item"])

def save_entries(entries: DailyEntries) -> None:
    table.put_item(Item={
        "pk": f"USER#{USER_ID}",
        "sk": f"ENTRY#{entries.date.isoformat()}",
        **entries.model_dump(mode="json")
    })
```

## Multi-User Migration Path

When ready to support multiple users:

1. **Extract user ID from auth context** (Cloudflare Access header or Cognito JWT)
2. **Replace `USER_ID = "default"` with dynamic user ID extraction**
3. **No schema changes required** - partition key already scoped to user

For IAM-based isolation (if using Cognito instead of Cloudflare Access):

```json
{
  "Effect": "Allow",
  "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query"],
  "Resource": "arn:aws:dynamodb:*:*:table/habit-tracker",
  "Condition": {
    "ForAllValues:StringEquals": {
      "dynamodb:LeadingKeys": ["USER#${cognito-identity.amazonaws.com:sub}"]
    }
  }
}
```

## Capacity Estimation

For a single user with 10 habits, daily tracking:

| Operation | Size | RCU/WCU | Daily Volume | Monthly Cost |
|-----------|------|---------|--------------|--------------|
| Load habits | ~2 KB | 1 RCU | 10-20 reads | Free tier |
| Load entries | ~1 KB | 1 RCU | 10-20 reads | Free tier |
| Save entries | ~1 KB | 1 WCU | 5-10 writes | Free tier |

DynamoDB free tier: 25 GB storage, 25 WCU, 25 RCU. This workload uses <0.01% of free tier.

## Code References

- `src/habit_tracker/models.py:1-82` - Current Pydantic models (Habit and HabitEntry discriminated unions)
- `src/habit_tracker/storage.py:1-50` - Current JSON file storage layer (to be replaced)
- `src/habit_tracker/main.py:25-43` - Index route showing load pattern (habits + entries per day)
- `src/habit_tracker/main.py:46-79` - Save route showing atomic save of all entries for a day

## Architecture Notes

### Patterns Used

1. **Entity-type prefixing**: `HABIT#`, `ENTRY#` prefixes in sort keys distinguish item types
2. **Composite sort keys**: Date embedded in sort key (`ENTRY#2025-01-15`) enables range queries
3. **Denormalized daily entries**: All habit entries for a day stored in single item (matches access pattern)
4. **User-scoped partitions**: All data for a user shares partition key prefix for isolation

### Patterns Deferred

1. **GSIs**: Not needed for current access patterns; add when analytics/admin views require them
2. **Write sharding**: Single-user workload doesn't approach partition limits (3000 RCU / 1000 WCU per partition)
3. **TTL**: No data expiration requirements yet; could add for old entries if storage becomes concern

## Open Questions

1. **Habit ordering**: Should `sort_order` be stored on each habit, or derive order from creation time? Current design includes `sort_order` attribute.

2. **Soft deletes**: When a habit is deleted, should entries be retained? Current design would leave orphaned entries (not necessarily wrong - historical data preserved).

3. **Entry history**: Should daily entries be versioned to track changes? Current design overwrites previous entries (matches current behavior).

4. **Batch operations**: If adding/importing many habits at once, should we use `BatchWriteItem`? Yes, for efficiency, but implementation detail.

## Sources

- [The What, Why, and When of Single-Table Design with DynamoDB](https://www.alexdebrie.com/posts/dynamodb-single-table/) - Alex DeBrie
- [DynamoDB Design Patterns for Single Table Design](https://www.serverlesslife.com/DynamoDB_Design_Patterns_for_Single_Table_Design.html) - Serverless Life
- [Part 1: Refactoring to single-table design in Amazon DynamoDB](https://emshea.com/post/part-1-dynamodb-single-table-design) - Em Shea
- [Amazon DynamoDB data modeling for Multi-Tenancy](https://aws.amazon.com/blogs/database/amazon-dynamodb-data-modeling-for-multi-tenancy-part-1/) - AWS Database Blog
- [Best practices for designing and using partition keys effectively](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-partition-key-design.html) - AWS Documentation
