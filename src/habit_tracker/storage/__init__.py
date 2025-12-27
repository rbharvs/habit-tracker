import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from .json_storage import JsonFileStorage
from .protocol import StorageProtocol


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
