from functools import lru_cache
from pathlib import Path

from fastapi import Depends

from ai_knowledge_hub_api.config import Settings, get_settings
from ai_knowledge_hub_api.storage.local import LocalDocumentStorage


@lru_cache
def _storage_for_root(root: str) -> LocalDocumentStorage:
    return LocalDocumentStorage(Path(root))


def document_storage_for_settings(settings: Settings) -> LocalDocumentStorage:
    resolved = settings.resolved_document_storage_root
    return _storage_for_root(str(resolved))


def get_document_storage(
    settings: Settings = Depends(get_settings),
) -> LocalDocumentStorage:
    return document_storage_for_settings(settings)


def clear_document_storage_cache() -> None:
    _storage_for_root.cache_clear()
