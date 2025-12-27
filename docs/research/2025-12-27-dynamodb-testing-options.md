# Research: DynamoDB Integration Testing Options

**Date**: 2025-12-27T02:49:54Z
**Git Commit**: 8da29ab8fa92e0ab82e6d2eda59d77fff5eed152
**Branch**: main

## Research Question

What are the local integration testing options for DynamoDB as they relate to our planned migration (see `docs/research/2025-12-27-dynamodb-single-table-design.md`), and how do they fit with our current testing setup? Ideally without running a Java application (DynamoDB Local).

## Summary

**Recommendation: Moto** is the best fit for this project.

Moto is a pure-Python library that mocks AWS services at the SDK level. It requires no Java, no Docker, and integrates seamlessly with pytest. It supports all DynamoDB operations needed for the habit-tracker's access patterns (`GetItem`, `PutItem`, `Query`).

| Option | Java Required | Docker Required | Speed | Fidelity |
|--------|--------------|-----------------|-------|----------|
| **Moto** | No | No | Fast (~40% faster than Local) | Good for unit/integration |
| DynamoDB Local | Yes (JRE 11+) | Optional | Slower | High |
| LocalStack | No (uses Docker) | Yes | Slower | High |
| Testcontainers | No | Yes | Slowest (container spin-up) | High |

For a personal habit tracker with straightforward DynamoDB usage (no Global Tables, no Streams, no complex transactions), Moto provides sufficient fidelity while being faster and simpler to set up.

## Current Testing Setup

The project uses:
- **pytest** (>=8.0.0) with **pytest-asyncio** (>=0.24.0)
- **httpx** for async FastAPI testing with `ASGITransport`
- Module-level patching of `storage` module variables for isolation

### Key Pattern: Storage Layer Patching

All tests use a fixture that patches the `storage` module's paths:

```python
# tests/test_storage.py, tests/test_main.py, tests/test_e2e.py
@pytest.fixture(autouse=True)
def clean_test_data():
    from habit_tracker import storage
    test_dir = Path("test_data")
    storage.DATA_DIR = test_dir
    storage.CONFIG_FILE = test_dir / "config.json"
    storage.ENTRIES_DIR = test_dir / "entries"
    yield
    shutil.rmtree(test_dir, ignore_errors=True)
```

This pattern is directly analogous to how Moto testing works: inject mocked infrastructure before tests run.

### Test File Structure

| File | Purpose | Approach |
|------|---------|----------|
| `tests/test_models.py` | Pydantic model validation | Pure unit tests, no storage |
| `tests/test_storage.py` | Storage layer CRUD | Patches storage paths |
| `tests/test_main.py` | FastAPI route tests | Patches storage, uses httpx |
| `tests/test_e2e.py` | End-to-end flow | Patches storage, uses httpx |

## DynamoDB Testing Options

### 1. Moto (Recommended)

Moto mocks AWS services at the boto3 SDK level. No external processes or containers.

**Installation:**
```toml
# pyproject.toml dev-dependencies
"moto[dynamodb]>=5.0.0"
```

**Pytest Fixture Pattern:**
```python
# conftest.py
import os
import pytest
import boto3
from moto import mock_aws

@pytest.fixture(scope="function")
def aws_credentials():
    """Set fake AWS credentials."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

@pytest.fixture(scope="function")
def dynamodb_table(aws_credentials):
    """Create mocked DynamoDB table."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName="habit-tracker",
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
        yield boto3.resource("dynamodb", region_name="us-east-1").Table("habit-tracker")
```

**Supported Operations:**
- All operations used in our planned schema: `GetItem`, `PutItem`, `Query`, `BatchWriteItem`
- Table management: `CreateTable`, `DeleteTable`, `DescribeTable`
- Transactions: `TransactGetItems`, `TransactWriteItems`

**Limitations:**
- Global Tables not supported (not needed for habit-tracker)
- Kinesis Streams not supported (not needed)
- Some edge cases in query/filter expressions may differ

**Advantages:**
- Pure Python, no external dependencies
- Fast execution (~40% faster than DynamoDB Local)
- Automatic cleanup between tests (data is ephemeral within mock context)
- Same pytest patterns already used in the project

### 2. DynamoDB Local

AWS's official local emulator. Runs as a Java process.

**Requirements:**
- JRE 11+ (DynamoDB Local 2.x, required since January 2025)
- ~500MB disk space

**Docker usage (avoids local Java install):**
```bash
docker run -p 8000:8000 amazon/dynamodb-local
```

**Configuration:**
```python
# Point boto3 to local endpoint
dynamodb = boto3.resource(
    "dynamodb",
    endpoint_url="http://localhost:8000"
)
```

**Advantages:**
- Highest fidelity to production DynamoDB
- Validates key schemas and attribute types
- Returns accurate error messages

**Disadvantages:**
- Requires Java or Docker
- Slower startup and test execution
- Extra process management in CI/CD
- pytest-dynamodb plugin available but adds complexity

### 3. LocalStack

Full AWS emulator using Docker. Uses DynamoDB Local internally.

**Requirements:**
- Docker

**Usage:**
```bash
docker run -p 4566:4566 localstack/localstack
```

**Configuration:**
```python
dynamodb = boto3.resource(
    "dynamodb",
    endpoint_url="http://localhost:4566"
)
```

**Advantages:**
- Supports 100+ AWS services
- Good for multi-service integration tests
- AWS Toolkit for VS Code integration

**Disadvantages:**
- Overkill for DynamoDB-only testing
- Heavier than Moto or DynamoDB Local
- Docker required

### 4. Testcontainers

Spins up DynamoDB Local (or LocalStack) in Docker per test/session.

**Requirements:**
- Docker
- testcontainers-python package

**Usage:**
```python
from testcontainers.dynamodb import DynamoDBContainer

def test_with_dynamodb():
    with DynamoDBContainer() as dynamodb:
        client = boto3.client(
            "dynamodb",
            endpoint_url=dynamodb.get_url()
        )
        # test code
```

**Advantages:**
- Ephemeral containers per test
- No cleanup needed
- Works in CI/CD with Docker

**Disadvantages:**
- Container spin-up adds 20-60 seconds per test session
- Still requires DynamoDB Local's Java runtime inside container

## Compatibility with Current Test Patterns

### Migration Path

The current storage layer (`src/habit_tracker/storage.py`) uses module-level variables that get patched in tests. The DynamoDB version would follow the same pattern:

**Current (JSON file storage):**
```python
# storage.py
DATA_DIR = Path("data")

def load_habits() -> list[Habit]:
    ...
```

**After migration (DynamoDB):**
```python
# storage.py
import boto3
import os

TABLE_NAME = os.environ.get("TABLE_NAME", "habit-tracker")
dynamodb = boto3.resource("dynamodb")

def get_table():
    return dynamodb.Table(TABLE_NAME)

def load_habits() -> list[Habit]:
    ...
```

**Test fixture approach:**
```python
# conftest.py
@pytest.fixture(autouse=True)
def mock_dynamodb():
    with mock_aws():
        # Create table
        boto3.client("dynamodb").create_table(...)
        # Patch the module's dynamodb resource
        from habit_tracker import storage
        storage.dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        yield
```

### Test Categories After Migration

| Test Type | Approach |
|-----------|----------|
| Model tests (`test_models.py`) | No changes needed |
| Storage tests (`test_storage.py`) | Use Moto fixtures |
| Route tests (`test_main.py`) | Use Moto fixtures (storage layer mocked) |
| E2E tests (`test_e2e.py`) | Use Moto fixtures |

### CI/CD Considerations

Moto requires no additional services in CI/CD pipelines:

```yaml
# GitHub Actions example
- name: Run tests
  run: uv run pytest
```

No Docker-in-Docker, no sidecar containers, no Java runtime.

## Code References

- `src/habit_tracker/storage.py:1-50` - Current storage implementation to be replaced
- `tests/test_storage.py:10-20` - Current fixture pattern for test isolation
- `tests/test_main.py:13-22` - Storage patching in route tests
- `docs/research/2025-12-27-dynamodb-single-table-design.md:182-227` - Planned DynamoDB storage implementation

## Architecture Notes

### Patterns Identified

1. **Module-level patching**: Tests patch storage module variables rather than using dependency injection
2. **Synchronous storage layer**: Current storage is sync; DynamoDB SDK (boto3) is also sync
3. **Fixture-based isolation**: `autouse=True` fixtures ensure clean state per test

### Patterns to Maintain

- Keep using `autouse=True` fixtures for test isolation
- Continue patching module-level resources (DynamoDB table instead of file paths)
- Maintain sync storage interface (boto3 is synchronous)

## Open Questions

1. **Async vs sync storage**: The current storage layer is synchronous, but FastAPI routes are async. Should the new DynamoDB layer use aiobotocore for async operations? (Moto does not fully support aiobotocore.)

2. **Table creation in tests**: Should each test create/delete the table, or use a session-scoped fixture? (Session-scoped with function-scoped data cleanup is faster.)

3. **Local development**: How should developers run the app locally? Options:
   - Use real DynamoDB (AWS credentials required)
   - Use Moto in a standalone server mode
   - Use DynamoDB Local via Docker

## Sources

- [Moto Documentation - Getting Started](https://docs.getmoto.org/en/latest/docs/getting_started.html)
- [Moto DynamoDB Support](https://docs.getmoto.org/en/latest/docs/services/dynamodb.html)
- [moto on PyPI](https://pypi.org/project/moto/)
- [Amazon DynamoDB Local Docker Image](https://hub.docker.com/r/amazon/dynamodb-local/)
- [DynamoDB Local 1.x End of Support](https://repost.aws/articles/AR3JPKxzfSQ--ZhOwXMKPZyg/amazon-dynamodb-local-1-x-end-of-support-is-january-2025)
- [Setting up DynamoDB Local - AWS Documentation](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.html)
- [Easier DynamoDB Unit Testing with Python - Trek10](https://www.trek10.com/blog/easier-dynamodb-unit-testing-with-python)
- [Effective AWS Mocking with Moto - Caylent](https://caylent.com/blog/mocking-aws-calls-using-moto)
- [LocalStack](https://www.localstack.cloud/)
