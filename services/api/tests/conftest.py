import pytest

from ai_knowledge_hub_api.config import get_settings
from ai_knowledge_hub_api.database import dispose_engine


@pytest.fixture(autouse=True)
def reset_settings_and_engine() -> None:
    get_settings.cache_clear()
    dispose_engine()
    yield
    dispose_engine()
    get_settings.cache_clear()
