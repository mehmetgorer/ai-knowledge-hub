import pytest
from pydantic import SecretStr

from ai_knowledge_hub_api.config import Settings


def test_resolved_database_url_from_postgres_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_DB", "app_db")
    monkeypatch.setenv("POSTGRES_USER", "app_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss:w@rd%23")
    monkeypatch.setenv("POSTGRES_HOST", "127.0.0.1")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = Settings()
    url = settings.resolved_database_url

    assert url.startswith("postgresql+psycopg://app_user:")
    assert "127.0.0.1:5433/app_db" in url
    assert "p@ss:w@rd%23" not in url


def test_database_url_override_takes_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    override = "postgresql+psycopg://override:secret@db.example.com:5432/prod"
    monkeypatch.setenv("DATABASE_URL", override)
    settings = Settings()
    assert settings.resolved_database_url == override


def test_postgres_password_is_secret() -> None:
    settings = Settings(postgres_password=SecretStr("hidden"))
    dumped = settings.model_dump()
    assert dumped["postgres_password"] != "hidden"
