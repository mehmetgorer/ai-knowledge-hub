import pytest

from ai_knowledge_hub_api.config import Settings


def test_default_cors_origins_include_local_frontend() -> None:
    settings = Settings()
    assert settings.cors_origins == ["http://localhost:3000"]


def test_cors_origins_parsed_from_comma_separated_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "http://localhost:3000,https://app.example.com",
    )
    settings = Settings()
    assert settings.cors_origins == [
        "http://localhost:3000",
        "https://app.example.com",
    ]


def test_service_name_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERVICE_NAME", "custom-api")
    settings = Settings()
    assert settings.service_name == "custom-api"
