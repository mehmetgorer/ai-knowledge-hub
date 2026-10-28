from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from ai_knowledge_hub_api.database import get_engine

_SessionLocal: sessionmaker[Session] | None = None


def _session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()


def reset_session_factory() -> None:
    global _SessionLocal
    _SessionLocal = None
