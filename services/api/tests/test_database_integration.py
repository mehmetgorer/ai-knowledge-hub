import pytest

from ai_knowledge_hub_api.database import ping_database


@pytest.mark.integration
def test_ping_database_against_local_postgres() -> None:
    """Requires Docker Compose PostgreSQL on POSTGRES_PORT (default 5433)."""
    assert ping_database() is True
