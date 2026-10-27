import pytest
from pydantic import SecretStr

from ai_knowledge_hub_api.config import Settings
from tests.alembic_test_support import (
    UnsafePostgresTargetError,
    alembic_subprocess_env,
    assert_local_postgres_host,
    assert_safe_temporary_database_name,
    build_database_url,
)


def test_alembic_subprocess_env_sets_database_url() -> None:
    env = alembic_subprocess_env(
        "postgresql+psycopg://user:pass%40@127.0.0.1:5433/alembic_test_x"
    )
    assert env["DATABASE_URL"] == (
        "postgresql+psycopg://user:pass%40@127.0.0.1:5433/alembic_test_x"
    )


def test_build_database_url_ignores_database_url_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://remote:secret@db.example.com:5432/production",
    )
    settings = Settings(
        postgres_host="127.0.0.1",
        postgres_port=5433,
        postgres_user="local_user",
        postgres_password=SecretStr("local_pass"),
        postgres_db="ai_knowledge_hub",
    )
    url = build_database_url(settings, "alembic_test_abc")
    assert "127.0.0.1:5433/alembic_test_abc" in url
    assert "db.example.com" not in url


def test_assert_local_postgres_host_rejects_remote() -> None:
    with pytest.raises(UnsafePostgresTargetError, match="local PostgreSQL"):
        assert_local_postgres_host("db.example.com")


def test_assert_safe_temporary_database_name_rejects_main_database() -> None:
    with pytest.raises(UnsafePostgresTargetError, match="main application database"):
        assert_safe_temporary_database_name("ai_knowledge_hub", "ai_knowledge_hub")


def test_assert_safe_temporary_database_name_requires_prefix() -> None:
    with pytest.raises(UnsafePostgresTargetError, match="alembic_test_"):
        assert_safe_temporary_database_name("scratch_db", "ai_knowledge_hub")
