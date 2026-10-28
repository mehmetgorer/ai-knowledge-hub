"""Integration tests for Collection API (temporary PostgreSQL database)."""

import uuid

import httpx
import pytest
from sqlalchemy import create_engine, text

from ai_knowledge_hub_api.app import create_app
from ai_knowledge_hub_api.auth.dependencies import (
    get_current_subject,
    get_jwks_resolver,
)
from ai_knowledge_hub_api.auth.jwks import StaticJwksResolver
from ai_knowledge_hub_api.config import Settings, get_settings
from ai_knowledge_hub_api.database import dispose_engine
from ai_knowledge_hub_api.migrations import ALEMBIC_HEAD_REVISION
from tests.alembic_test_support import (
    assert_local_postgres_host,
    assert_safe_temporary_database_name,
    build_database_url,
    read_alembic_revision,
    run_alembic,
)
from tests.auth_keys import (
    TEST_ISSUER,
    TEST_JWKS_URL,
    Ed25519KeyPair,
    generate_ed25519_key_pair,
    mint_access_token,
)

_TEMPORARY_DATABASE_PREFIX = "alembic_test_"


def _admin_engine(settings: Settings):
    return create_engine(
        build_database_url(settings, "postgres"),
        isolation_level="AUTOCOMMIT",
    )


@pytest.fixture
def auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_JWKS_URL", TEST_JWKS_URL)
    monkeypatch.setenv("AUTH_ISSUER", TEST_ISSUER)
    monkeypatch.setenv("AUTH_AUDIENCE", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def key_pair() -> Ed25519KeyPair:
    return generate_ed25519_key_pair()


@pytest.fixture
def migrated_collections_database(monkeypatch: pytest.MonkeyPatch) -> str:
    get_settings.cache_clear()
    settings = Settings()
    assert_local_postgres_host(settings.postgres_host)

    main_database = settings.postgres_db
    main_url = build_database_url(settings, main_database)
    main_revision_before = read_alembic_revision(main_url)

    db_name = f"{_TEMPORARY_DATABASE_PREFIX}collections_{uuid.uuid4().hex[:8]}"
    assert_safe_temporary_database_name(db_name, main_database)
    temp_url = build_database_url(settings, db_name)

    with _admin_engine(settings).connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{db_name}"'))

    try:
        result = run_alembic("upgrade", "head", database_url=temp_url)
        assert result.returncode == 0, result.stderr
        assert read_alembic_revision(temp_url) == ALEMBIC_HEAD_REVISION

        monkeypatch.setenv("DATABASE_URL", temp_url)
        get_settings.cache_clear()
        dispose_engine()
        yield temp_url
    finally:
        get_settings.cache_clear()
        dispose_engine()
        assert_safe_temporary_database_name(db_name, main_database)
        with _admin_engine(settings).connect() as connection:
            connection.execute(
                text(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = :dbname AND pid <> pg_backend_pid()
                    """
                ),
                {"dbname": db_name},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))

        assert read_alembic_revision(main_url) == main_revision_before


def _client_for_subject(
    key_pair: Ed25519KeyPair,
    subject: str,
) -> httpx.AsyncClient:
    app = create_app()
    app.dependency_overrides[get_jwks_resolver] = lambda: StaticJwksResolver(
        {key_pair.kid: key_pair.public_key}
    )
    app.dependency_overrides[get_current_subject] = lambda: subject
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.integration
@pytest.mark.anyio
async def test_create_and_list_collections_persisted(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_collections_database: str,
) -> None:
    del migrated_collections_database

    async with _client_for_subject(key_pair, "neon-user-a") as client:
        create_response = await client.post(
            "/collections",
            json={"name": "  Research Notes  "},
        )
        assert create_response.status_code == 201
        body = create_response.json()
        assert body["name"] == "Research Notes"
        assert "id" in body
        assert "created_at" in body
        assert "updated_at" in body
        assert "owner_subject" not in body

        list_response = await client.get("/collections")
        assert list_response.status_code == 200
        items = list_response.json()
        assert len(items) == 1
        assert items[0]["id"] == body["id"]


@pytest.mark.integration
@pytest.mark.anyio
async def test_collections_isolated_between_subjects(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_collections_database: str,
) -> None:
    del migrated_collections_database

    async with _client_for_subject(key_pair, "neon-user-a") as client_a:
        first = await client_a.post("/collections", json={"name": "Team A"})
        second = await client_a.post("/collections", json={"name": "Team B"})
        assert first.status_code == 201
        assert second.status_code == 201

        listed_a = await client_a.get("/collections")
        assert listed_a.status_code == 200
        names_a = [item["name"] for item in listed_a.json()]
        assert names_a == ["Team B", "Team A"]

    async with _client_for_subject(key_pair, "neon-user-b") as client_b:
        listed_b = await client_b.get("/collections")
        assert listed_b.status_code == 200
        assert listed_b.json() == []


@pytest.mark.integration
@pytest.mark.anyio
async def test_collection_create_uses_verified_subject_not_client_body(
    auth_env: None,
    key_pair: Ed25519KeyPair,
    migrated_collections_database: str,
) -> None:
    del migrated_collections_database

    token = mint_access_token(key_pair, subject="verified-subject-only")
    app = create_app()
    app.dependency_overrides[get_jwks_resolver] = lambda: StaticJwksResolver(
        {key_pair.kid: key_pair.public_key}
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/collections",
            json={"name": "Private", "owner_subject": "forged-subject"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201

    async with _client_for_subject(key_pair, "forged-subject") as client:
        forged_list = await client.get("/collections")
        assert forged_list.json() == []

    async with _client_for_subject(key_pair, "verified-subject-only") as client:
        owner_list = await client.get("/collections")
        assert len(owner_list.json()) == 1
