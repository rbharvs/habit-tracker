import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from .json_storage import JsonFileStorage
from .protocol import StorageProtocol


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


# Type alias for dependency injection
Storage = Annotated[StorageProtocol, Depends(get_storage)]
