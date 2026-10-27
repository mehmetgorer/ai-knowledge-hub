"""Helpers for safe Alembic integration tests (local PostgreSQL only)."""

import os
import subprocess
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ProgrammingError

from ai_knowledge_hub_api.config import Settings

LOCAL_POSTGRES_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
TEMPORARY_DATABASE_PREFIX = "alembic_test_"

_API_ROOT = Path(__file__).resolve().parents[1]


class UnsafePostgresTargetError(RuntimeError):
    """Raised when a test would touch a non-local or non-temporary database."""


def assert_local_postgres_host(host: str) -> None:
    if host.strip().lower() not in LOCAL_POSTGRES_HOSTS:
        raise UnsafePostgresTargetError(
            "Alembic integration tests may only run against local PostgreSQL hosts "
            f"({', '.join(sorted(LOCAL_POSTGRES_HOSTS))}); got {host!r}."
        )


def assert_safe_temporary_database_name(db_name: str, main_database: str) -> None:
    if db_name == main_database:
        raise UnsafePostgresTargetError(
            "Refusing to run destructive Alembic test operations on the main "
            f"application database ({main_database!r})."
        )
    if not db_name.startswith(TEMPORARY_DATABASE_PREFIX):
        raise UnsafePostgresTargetError(
            "Temporary test database names must start with "
            f"{TEMPORARY_DATABASE_PREFIX!r}; got {db_name!r}."
        )


def build_database_url(settings: Settings, database: str) -> str:
    """Build a URL from POSTGRES_* fields (ignores DATABASE_URL override)."""
    assert_local_postgres_host(settings.postgres_host)
    return URL.create(
        drivername="postgresql+psycopg",
        username=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=database,
    ).render_as_string(hide_password=False)


def alembic_subprocess_env(database_url: str) -> dict[str, str]:
    """Environment for Alembic subprocesses targeting a specific database URL."""
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    return env


def run_alembic(
    *args: str,
    database_url: str,
) -> subprocess.CompletedProcess[str]:
    assert_local_postgres_host(_host_from_database_url(database_url))
    return subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=_API_ROOT,
        env=alembic_subprocess_env(database_url),
        capture_output=True,
        text=True,
        check=False,
    )


def _host_from_database_url(database_url: str) -> str:
    return make_url(database_url).host or ""


def read_alembic_revision(database_url: str) -> str | None:
    with create_engine(database_url).connect() as connection:
        try:
            row = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).first()
        except ProgrammingError:
            connection.rollback()
            return None
        return row[0] if row else None
