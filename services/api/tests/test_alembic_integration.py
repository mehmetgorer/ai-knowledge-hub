import uuid

import pytest
from sqlalchemy import create_engine, text

from ai_knowledge_hub_api.config import Settings, get_settings
from ai_knowledge_hub_api.migrations import ALEMBIC_HEAD_REVISION
from tests.alembic_test_support import (
    assert_local_postgres_host,
    assert_safe_temporary_database_name,
    build_database_url,
    read_alembic_revision,
    run_alembic,
)

_TEMPORARY_DATABASE_PREFIX = "alembic_test_"


def _admin_engine(settings: Settings):
    admin_url = build_database_url(settings, "postgres")
    return create_engine(admin_url, isolation_level="AUTOCOMMIT")


@pytest.mark.integration
def test_alembic_upgrade_downgrade_on_temporary_database() -> None:
    get_settings.cache_clear()
    settings = Settings()
    assert_local_postgres_host(settings.postgres_host)

    main_database = settings.postgres_db
    main_url = build_database_url(settings, main_database)
    main_revision_before = read_alembic_revision(main_url)

    db_name = f"{_TEMPORARY_DATABASE_PREFIX}{uuid.uuid4().hex[:12]}"
    assert_safe_temporary_database_name(db_name, main_database)
    temp_url = build_database_url(settings, db_name)

    with _admin_engine(settings).connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{db_name}"'))

    try:
        assert read_alembic_revision(temp_url) is None

        upgrade = run_alembic("upgrade", "head", database_url=temp_url)
        assert upgrade.returncode == 0, upgrade.stderr
        assert read_alembic_revision(temp_url) == ALEMBIC_HEAD_REVISION

        upgrade_again = run_alembic("upgrade", "head", database_url=temp_url)
        assert upgrade_again.returncode == 0, upgrade_again.stderr

        current = run_alembic("current", database_url=temp_url)
        assert current.returncode == 0, current.stderr
        assert ALEMBIC_HEAD_REVISION in current.stdout

        downgrade = run_alembic("downgrade", "base", database_url=temp_url)
        assert downgrade.returncode == 0, downgrade.stderr
        assert read_alembic_revision(temp_url) is None

        upgrade_after_downgrade = run_alembic("upgrade", "head", database_url=temp_url)
        assert upgrade_after_downgrade.returncode == 0, upgrade_after_downgrade.stderr
        assert read_alembic_revision(temp_url) == ALEMBIC_HEAD_REVISION

        with create_engine(temp_url).connect() as connection:
            row = connection.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).fetchone()
            assert row is not None

        assert read_alembic_revision(main_url) == main_revision_before
    finally:
        get_settings.cache_clear()
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
