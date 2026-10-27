import os
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from ai_knowledge_hub_api.config import Settings, get_settings

_API_ROOT = Path(__file__).resolve().parents[1]


def _admin_engine(settings: Settings):
    admin_url = URL.create(
        drivername="postgresql+psycopg",
        username=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        host=settings.postgres_host,
        port=settings.postgres_port,
        database="postgres",
    )
    return create_engine(admin_url, isolation_level="AUTOCOMMIT")


def _database_url(settings: Settings, database: str) -> str:
    return URL.create(
        drivername="postgresql+psycopg",
        username=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=database,
    ).render_as_string(hide_password=False)


def _run_alembic(*args: str, postgres_db: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["POSTGRES_DB"] = postgres_db
    env.pop("DATABASE_URL", None)
    return subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=_API_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.integration
def test_alembic_upgrade_downgrade_on_temporary_database() -> None:
    get_settings.cache_clear()
    settings = Settings()
    db_name = f"alembic_test_{uuid.uuid4().hex[:12]}"

    with _admin_engine(settings).connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{db_name}"'))

    try:
        upgrade = _run_alembic("upgrade", "head", postgres_db=db_name)
        assert upgrade.returncode == 0, upgrade.stderr

        upgrade_again = _run_alembic("upgrade", "head", postgres_db=db_name)
        assert upgrade_again.returncode == 0, upgrade_again.stderr

        current = _run_alembic("current", postgres_db=db_name)
        assert current.returncode == 0, current.stderr
        assert "0001_enable_vector" in current.stdout

        downgrade = _run_alembic("downgrade", "base", postgres_db=db_name)
        assert downgrade.returncode == 0, downgrade.stderr

        upgrade_after_downgrade = _run_alembic(
            "upgrade",
            "head",
            postgres_db=db_name,
        )
        assert upgrade_after_downgrade.returncode == 0, upgrade_after_downgrade.stderr

        with create_engine(_database_url(settings, db_name)).connect() as connection:
            row = connection.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).fetchone()
            assert row is not None
    finally:
        get_settings.cache_clear()
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
