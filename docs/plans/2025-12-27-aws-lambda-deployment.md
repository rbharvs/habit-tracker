# Implementation Plan: AWS Lambda + DynamoDB Deployment

**Date**: 2025-12-27T03:09:02Z
**Git Commit**: 8da29ab8fa92e0ab82e6d2eda59d77fff5eed152
**Branch**: main

## Overview

Deploy the habit-tracker application to AWS Lambda with DynamoDB storage and Cloudflare Access authentication. This involves:

1. Removing asyncio (simplifying to sync routes)
2. Creating a storage abstraction layer supporting both JSON and DynamoDB
3. Adding Mangum for Lambda integration and SAM for infrastructure
4. Setting up CI/CD with GitHub Actions and OIDC
5. Configuring Cloudflare Access for authentication

## Current State

- **Framework**: FastAPI with async routes (`src/habit_tracker/main.py:25-79`)
- **Storage**: JSON file-based (`src/habit_tracker/storage.py:1-49`) with module-level path variables
- **Tests**: Use `pytest-asyncio` with module-level patching of storage paths
- **Dependencies**: FastAPI, uvicorn, Jinja2, Pydantic (`pyproject.toml:9-15`)
- **Dev workflow**: `make fix` (format + lint + typecheck), `make test`, `make dev`

## Desired End State

- Sync FastAPI routes running on AWS Lambda via Mangum
- Storage abstraction with `Protocol` supporting JSON (local dev) and DynamoDB (production)
- SAM template for Lambda + DynamoDB + API Gateway
- `make deploy` command for production deployment
- GitHub Actions: `integrate` (on push) and `deploy` (workflow_dispatch)
- Cloudflare Access protecting the API with Google OAuth

### Verification

1. `make test` passes with both JSON and DynamoDB (moto) storage backends
2. `make deploy` successfully deploys to AWS
3. Application accessible at `https://habits.yourdomain.com` with Google login

## What We're NOT Doing

- Multi-user support (hardcoded `USER#default` partition key)
- EventBridge keep-warm rule (can add later if cold starts are problematic)
- Custom domain in SAM (Cloudflare handles this)
- Static file serving from Lambda (CSS/JS already from CDN)
- Async DynamoDB operations (boto3 sync is fine for Lambda)

## Implementation Approach

The work is divided into 5 phases, each producing a working, testable state:

1. **Remove asyncio** - Convert routes to sync, update tests
2. **Storage abstraction** - Protocol + JSON implementation (behavior unchanged)
3. **DynamoDB implementation** - Add DynamoDB storage, moto tests
4. **Lambda + SAM** - Mangum handler, SAM template, deployment
5. **CI/CD** - GitHub Actions workflows with OIDC

Cloudflare Access is a manual step documented at the end.

---

## Phase 1: Remove Asyncio

### Overview

Convert async routes to sync and remove pytest-asyncio. This simplifies the codebase and is better suited for Lambda's execution model.

### Changes Required

#### `src/habit_tracker/main.py`

**File**: `src/habit_tracker/main.py`

Convert async routes to sync. For form data (which requires `await`), use an async dependency:

```python
# Add async dependency for form data
async def get_form_data(request: Request) -> FormData:
    """Parse form data asynchronously for use in sync routes."""
    return await request.form()
```

```python
# Change from:
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, day: str | None = None) -> HTMLResponse:
    ...

# To:
@app.get("/", response_class=HTMLResponse)
def index(request: Request, day: str | None = None) -> HTMLResponse:
    ...
```

```python
# Change from:
@app.post("/save", response_model=None)
async def save(request: Request) -> Response:
    form = await request.form()
    ...

# To:
@app.post("/save", response_model=None)
def save(request: Request, form: FormData = Depends(get_form_data)) -> Response:
    ...
```

Also add necessary imports:
```python
from fastapi import Depends
from starlette.datastructures import FormData
```

#### `pyproject.toml`

**File**: `pyproject.toml:18-24`

Remove `pytest-asyncio` from dev dependencies:

```toml
[tool.uv]
dev-dependencies = [
    "pytest>=8.0.0",
    "httpx>=0.27.0",
    "ruff>=0.8.0",
    "ty>=0.0.1a6",
]
```

#### Test files

**Files**: `tests/test_main.py`, `tests/test_e2e.py`

Replace `AsyncClient` with `TestClient` and remove `@pytest.mark.asyncio`:

```python
# Change from:
from httpx import ASGITransport, AsyncClient

@pytest.mark.asyncio
async def test_index_returns_html():
    from habit_tracker.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
        ...

# To:
from fastapi.testclient import TestClient

def test_index_returns_html():
    from habit_tracker.main import app
    client = TestClient(app)
    response = client.get("/")
    ...
```

### Success Criteria

#### Automated Verification:
- [x] `make test` passes (all 24 tests)
- [x] `make fix` passes (format, lint, typecheck)
- [x] No `async def` in `main.py` (routes are sync; `get_form_data` dependency is async as designed)
- [x] No `pytest-asyncio` in `pyproject.toml`

#### Manual Verification:
- [x] `make dev` starts server, app works at `localhost:8000`

---

## Phase 2: Storage Abstraction Layer

### Overview

Introduce a `StorageProtocol` and refactor the JSON storage into a class. Routes use dependency injection. This phase doesn't change behavior—just structure.

### Changes Required

#### New file: `src/habit_tracker/storage/protocol.py`

```python
from datetime import date
from typing import Protocol

from habit_tracker.models import DailyEntries, Habit


class StorageProtocol(Protocol):
    """Protocol defining the storage interface for habit tracking."""

    def load_habits(self) -> list[Habit]: ...
    def save_habits(self, habits: list[Habit]) -> None: ...
    def load_entries(self, day: date) -> DailyEntries | None: ...
    def save_entries(self, entries: DailyEntries) -> None: ...
```

#### New file: `src/habit_tracker/storage/json_storage.py`

Move current storage logic into a `JsonFileStorage` class:

```python
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import json

from pydantic import TypeAdapter
from habit_tracker.models import DailyEntries, Habit


@dataclass
class JsonFileStorage:
    """JSON file-based storage implementation."""

    data_dir: Path

    def __post_init__(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.entries_dir.mkdir(exist_ok=True)

    @property
    def config_file(self) -> Path:
        return self.data_dir / "config.json"

    @property
    def entries_dir(self) -> Path:
        return self.data_dir / "entries"

    def load_habits(self) -> list[Habit]:
        if not self.config_file.exists():
            return []
        adapter = TypeAdapter(list[Habit])
        data = json.loads(self.config_file.read_text())
        return adapter.validate_python(data.get("habits", []))

    def save_habits(self, habits: list[Habit]) -> None:
        data = {"habits": [h.model_dump() for h in habits]}
        self.config_file.write_text(json.dumps(data, indent=2))

    def load_entries(self, day: date) -> DailyEntries | None:
        path = self.entries_dir / f"{day.isoformat()}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return DailyEntries(**data)

    def save_entries(self, entries: DailyEntries) -> None:
        path = self.entries_dir / f"{entries.date.isoformat()}.json"
        path.write_text(json.dumps(entries.model_dump(), indent=2, default=str))
```

#### New file: `src/habit_tracker/storage/__init__.py`

```python
import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from .protocol import StorageProtocol
from .json_storage import JsonFileStorage


@lru_cache
def _get_json_storage() -> JsonFileStorage:
    """Get singleton JSON storage instance."""
    data_dir = Path(os.environ.get("DATA_DIR", "data"))
    return JsonFileStorage(data_dir=data_dir)


def get_storage() -> StorageProtocol:
    """Get storage implementation based on environment."""
    # Phase 2: JSON only. Phase 3 adds DynamoDB.
    return _get_json_storage()


# Type alias for dependency injection
Storage = Annotated[StorageProtocol, Depends(get_storage)]
```

#### Delete: `src/habit_tracker/storage.py`

Remove the old module-level storage file.

#### Update: `src/habit_tracker/main.py`

Change imports and add `storage: Storage` parameter to routes:

```python
# Change from:
from . import storage

# To:
from .storage import Storage

# Change routes to use injected storage:
@app.get("/", response_class=HTMLResponse)
def index(request: Request, storage: Storage, day: str | None = None) -> HTMLResponse:
    ...

@app.post("/save", response_model=None)
def save(
    request: Request,
    storage: Storage,
    form: FormData = Depends(get_form_data),
) -> Response:
    ...
```

#### Update: `tests/conftest.py` (new file)

```python
import shutil
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
```

#### Update test files

Remove the manual storage patching fixtures from `test_main.py`, `test_storage.py`, and `test_e2e.py`. The `conftest.py` fixture handles it.

Update `test_storage.py` to test `JsonFileStorage` directly:

```python
from habit_tracker.storage.json_storage import JsonFileStorage

def test_load_habits_returns_empty_list_when_no_config(tmp_path):
    storage = JsonFileStorage(data_dir=tmp_path / "data")
    habits = storage.load_habits()
    assert habits == []
```

### Success Criteria

#### Automated Verification:
- [x] `make test` passes
- [x] `make fix` passes
- [x] No imports from old `storage` module

#### Manual Verification:
- [x] `make dev` works, existing `data/` directory still loads

---

## Phase 3: DynamoDB Storage Implementation

### Overview

Add `DynamoDBStorage` class and moto-based tests. The app can now run with either backend based on `STORAGE_BACKEND` environment variable.

### Changes Required

#### `pyproject.toml`

Add boto3 to dependencies and moto + aws-sam-cli to dev dependencies:

```toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "jinja2>=3.1.0",
    "pydantic>=2.0.0",
    "python-multipart>=0.0.9",
    "boto3>=1.35.0",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0.0",
    "httpx>=0.27.0",
    "ruff>=0.8.0",
    "ty>=0.0.1a6",
    "moto[dynamodb]>=5.0.0",
    "aws-sam-cli>=1.130.0",
]
```

#### New file: `src/habit_tracker/storage/dynamodb_storage.py`

```python
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
            KeyConditionExpression=Key("pk").eq(self._user_pk()) & Key("sk").begins_with("HABIT#")
        )
        items = response.get("Items", [])
        # Sort by sort_order if present, then by id
        items.sort(key=lambda x: (x.get("sort_order", 999), x.get("id", "")))
        adapter = TypeAdapter(list[Habit])
        return adapter.validate_python([_from_dynamodb(item) for item in items])

    def save_habits(self, habits: list[Habit]) -> None:
        # Delete existing habits
        response = self._table.query(
            KeyConditionExpression=Key("pk").eq(self._user_pk()) & Key("sk").begins_with("HABIT#"),
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
                "entries": _to_dynamodb({k: v.model_dump() for k, v in entries.entries.items()}),
            }
        )
```

#### Update: `src/habit_tracker/storage/__init__.py`

```python
import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from .protocol import StorageProtocol
from .json_storage import JsonFileStorage


def _get_storage_backend() -> str:
    return os.environ.get("STORAGE_BACKEND", "json")


@lru_cache
def _get_json_storage() -> JsonFileStorage:
    data_dir = Path(os.environ.get("DATA_DIR", "data"))
    return JsonFileStorage(data_dir=data_dir)


@lru_cache
def _get_dynamodb_storage():
    from .dynamodb_storage import DynamoDBStorage
    return DynamoDBStorage(
        table_name=os.environ.get("TABLE_NAME", "habit-tracker"),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        endpoint_url=os.environ.get("DYNAMODB_ENDPOINT_URL"),
    )


def get_storage() -> StorageProtocol:
    """Get storage implementation based on STORAGE_BACKEND env var."""
    backend = _get_storage_backend()
    if backend == "dynamodb":
        return _get_dynamodb_storage()
    return _get_json_storage()


Storage = Annotated[StorageProtocol, Depends(get_storage)]
```

#### New file: `tests/test_dynamodb_storage.py`

```python
import os
from datetime import date

import boto3
import pytest
from moto import mock_aws

from habit_tracker.models import BinaryEntry, BinaryHabit, DailyEntries, SingleSelectHabit
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
```

### Success Criteria

#### Automated Verification:
- [x] `make test` passes (including new DynamoDB tests)
- [x] `make fix` passes

#### Manual Verification:
- [x] `STORAGE_BACKEND=json make dev` works
- [x] DynamoDB storage tests use moto (no real AWS calls)

---

## Phase 4: Lambda + SAM Integration

### Overview

Add Mangum handler and SAM template. Create `make deploy` command.

### Changes Required

#### `pyproject.toml`

Add mangum dependency:

```toml
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "jinja2>=3.1.0",
    "pydantic>=2.0.0",
    "python-multipart>=0.0.9",
    "boto3>=1.35.0",
    "mangum>=0.19.0",
]
```

#### New file: `src/habit_tracker/handler.py`

```python
"""AWS Lambda handler using Mangum."""
from mangum import Mangum

from habit_tracker.main import app

handler = Mangum(app, lifespan="off")
```

#### New file: `template.yaml`

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Habit Tracker - FastAPI on Lambda

Globals:
  Function:
    Timeout: 30
    Runtime: python3.12
    MemorySize: 256
    Architectures:
      - arm64

Resources:
  HabitApi:
    Type: AWS::Serverless::HttpApi

  HabitFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: habit-tracker
      Handler: habit_tracker.handler.handler
      CodeUri: src/
      Environment:
        Variables:
          STORAGE_BACKEND: dynamodb
          TABLE_NAME: !Ref HabitTable
          AWS_REGION: !Ref AWS::Region
      Events:
        Root:
          Type: HttpApi
          Properties:
            ApiId: !Ref HabitApi
            Path: /
            Method: ANY
        Proxy:
          Type: HttpApi
          Properties:
            ApiId: !Ref HabitApi
            Path: /{proxy+}
            Method: ANY
      Policies:
        - DynamoDBCrudPolicy:
            TableName: !Ref HabitTable
    Metadata:
      BuildMethod: python3.12

  HabitTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: habit-tracker
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: pk
          AttributeType: S
        - AttributeName: sk
          AttributeType: S
      KeySchema:
        - AttributeName: pk
          KeyType: HASH
        - AttributeName: sk
          KeyType: RANGE

Outputs:
  ApiUrl:
    Description: API Gateway URL (configure Cloudflare to point here)
    Value: !Sub https://${HabitApi}.execute-api.${AWS::Region}.amazonaws.com

  FunctionName:
    Description: Lambda function name
    Value: !Ref HabitFunction

  TableName:
    Description: DynamoDB table name
    Value: !Ref HabitTable
```

#### New file: `samconfig.toml`

```toml
version = 0.1

[default.global.parameters]
stack_name = "habit-tracker"

[default.build.parameters]
cached = true
parallel = true

[default.deploy.parameters]
capabilities = "CAPABILITY_IAM"
confirm_changeset = false
resolve_s3 = true
region = "us-east-1"
```

#### Update: `Makefile`

Add deployment commands:

```makefile
.PHONY: help fix format lint typecheck test dev browser clean build deploy check

# ... existing targets ...

build:  ## Build SAM application
	uv run sam build

deploy: build  ## Deploy to AWS Lambda
	uv run sam deploy
```

Note: For the first deployment, run `uv run sam deploy --guided` manually to set up the stack.

#### New file: `src/requirements.txt`

SAM needs a requirements.txt for the Lambda package:

```
fastapi>=0.115.0
jinja2>=3.1.0
pydantic>=2.0.0
python-multipart>=0.0.9
boto3>=1.35.0
mangum>=0.19.0
```

### Success Criteria

#### Automated Verification:
- [ ] `make build` succeeds
- [ ] `make test` still passes
- [ ] `make fix` passes

#### Manual Verification:
- [ ] `uv run sam deploy --guided` deploys to AWS (first time)
- [ ] `make deploy` works for subsequent deploys
- [ ] API Gateway URL returns the app (unauthenticated for now)
- [ ] DynamoDB table is created
- [ ] Can create habits and entries via the deployed app

---

## Phase 5: GitHub Actions CI/CD

### Overview

Add a `make check` target (check-only mode for CI) and two workflows:
1. `integrate.yml` - Runs on push, runs `make check` + `make test` (**no AWS access**)
2. `deploy.yml` - Manual trigger (workflow_dispatch), runs `make deploy`

The deploy workflow uses GitHub OIDC for AWS credentials (no long-lived secrets).

### Security Considerations (Public Repository)

Since this is a public repository, we must protect against malicious pull requests:

1. **OIDC Trust Policy**: Restricted to `ref:refs/heads/main` only. PRs (including from forks) cannot assume the AWS role.

2. **Workflow Separation**:
   - `integrate.yml` has **no AWS permissions** and runs on all pushes/PRs (safe)
   - `deploy.yml` has AWS permissions but only triggers via `workflow_dispatch` (manual)

3. **GitHub Environment**: The `production` environment with required reviewers adds a manual approval gate before any deploy.

4. **No PR-triggered deploys**: The deploy workflow uses `workflow_dispatch`, not `pull_request` or `push`. Only repo maintainers can trigger it.

### AWS Setup (One-time, Manual)

Before the workflows work, set up OIDC in AWS:

1. **Create OIDC Identity Provider in IAM**:
   - Provider URL: `https://token.actions.githubusercontent.com`
   - Audience: `sts.amazonaws.com`

2. **Create IAM Role** `GitHubActionsHabitTracker` with:
   - Trust policy for your repo (**restricted to main branch only**):
     ```json
     {
       "Version": "2012-10-17",
       "Statement": [{
         "Effect": "Allow",
         "Principal": {
           "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
         },
         "Action": "sts:AssumeRoleWithWebIdentity",
         "Condition": {
           "StringEquals": {
             "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
             "token.actions.githubusercontent.com:sub": "repo:YOUR_USERNAME/habit-tracker:ref:refs/heads/main"
           }
         }
       }]
     }
     ```
   - Permissions policy: `AdministratorAccess` (or scoped CloudFormation/Lambda/DynamoDB/S3/IAM permissions)

   > **Security Note (Public Repos)**: The `sub` claim uses `StringEquals` with the exact ref `ref:refs/heads/main`. This ensures only workflows triggered by pushes directly to `main` can assume the role. Pull requests (including from forks) cannot assume this role, protecting against malicious PRs.

3. **Add Repository Secret**:
   - `AWS_ROLE_ARN`: `arn:aws:iam::ACCOUNT_ID:role/GitHubActionsHabitTracker`

4. **Create GitHub Environment** `production`:
   - Settings → Environments → New environment → Name: `production`
   - Add protection rule: **Required reviewers** → Add yourself
   - This adds a manual approval gate before deploys (optional but recommended for public repos)

### Changes Required

#### Update: `Makefile`

Add a `check` target for CI (check-only, no auto-fix):

```makefile
check:  ## Check code (CI mode - no auto-fix)
	uv run ruff format --check src/ tests/
	uv run ruff check src/ tests/
	uv run ty check src/
```

#### New file: `.github/workflows/integrate.yml`

```yaml
name: Integrate

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

# No permissions block = no special permissions (safe for PRs from forks)

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --locked --dev

      - name: Check (format, lint, typecheck)
        run: make check

      - name: Test
        run: make test
```

#### New file: `.github/workflows/deploy.yml`

```yaml
name: Deploy

on:
  workflow_dispatch:

permissions:
  id-token: write
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production  # Requires approval if protection rules configured
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --locked --dev

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          aws-region: us-east-1

      - name: Deploy
        run: make deploy
```

### Success Criteria

#### Automated Verification:
- [ ] `make check` passes locally
- [ ] Push to `main` triggers integrate workflow
- [ ] Integrate workflow passes

#### Manual Verification:
- [ ] Workflow dispatch deploy works from GitHub UI
- [ ] Deployed app is accessible and functional
- [ ] IAM role trust policy uses `StringEquals` with exact `ref:refs/heads/main`
- [ ] GitHub Environment `production` exists with required reviewers enabled

---

## Cloudflare Access Setup (Manual)

After deployment, protect the API with Cloudflare Access:

### Prerequisites
- Domain managed by Cloudflare (free plan works)
- API Gateway URL from `make deploy` output

### Steps

1. **Add DNS Record**:
   - Type: CNAME
   - Name: `habits` (or your subdomain)
   - Target: `xxxxxxxxxx.execute-api.us-east-1.amazonaws.com`
   - Proxy: Enabled (orange cloud)

2. **Create Access Application**:
   - Zero Trust → Access → Applications → Add Application
   - Type: Self-hosted
   - Application domain: `habits.yourdomain.com`
   - Session duration: 1 month

3. **Add Policy**:
   - Name: Allow me
   - Action: Allow
   - Include: Emails → your email

4. **Configure CORS** (required for HTMX):
   - Settings → CORS
   - Access-Control-Allow-Credentials: Enabled
   - Access-Control-Max-Age: 86400
   - Access-Control-Allow-Origin: `https://habits.yourdomain.com`
   - Allow all methods: Enabled
   - Allow all headers: Enabled

5. **Add Google Login**:
   - Settings → Authentication → Login methods → Add → Google
   - (No credentials needed - Cloudflare uses its own OAuth app)

### Verification
- [ ] `https://habits.yourdomain.com` redirects to Google login
- [ ] After login, app loads and works
- [ ] Auto-save (HTMX POST) works without 403 errors

---

## Testing Strategy

### Existing Tests (Phases 1-2)
- `test_models.py` - Unchanged
- `test_storage.py` - Updated to test `JsonFileStorage` class
- `test_main.py` - Updated to sync, uses dependency override
- `test_e2e.py` - Updated to sync

### New Tests (Phase 3)
- `test_dynamodb_storage.py` - DynamoDB storage with moto

### Test Patterns
- All tests use `tmp_path` fixture for file isolation
- DynamoDB tests use `mock_aws` context manager
- FastAPI tests use `app.dependency_overrides` for storage injection

---

## Code References

- `src/habit_tracker/main.py:25-79` - Current async routes to convert
- `src/habit_tracker/storage.py:1-49` - Current storage to refactor
- `tests/test_main.py:10-22` - Current test fixture pattern to replace
- `docs/research/2025-12-27-dynamodb-single-table-design.md:64-127` - DynamoDB schema design
- `docs/research/2025-12-27-hosting-options.md:337-411` - SAM template reference
- `docs/research/2025-12-27-dynamodb-testing-options.md:73-106` - Moto fixture pattern
