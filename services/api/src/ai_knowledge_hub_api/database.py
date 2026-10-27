from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from ai_knowledge_hub_api.config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.resolved_database_url,
            pool_pre_ping=True,
            connect_args={
                "connect_timeout": int(settings.database_connect_timeout),
            },
        )
    return _engine


def ping_database() -> bool:
    """Return True when the database answers ``SELECT 1``."""
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def dispose_engine() -> None:
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None
