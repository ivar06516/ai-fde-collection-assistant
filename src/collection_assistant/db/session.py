from contextlib import contextmanager
from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from collection_assistant.config import get_settings
from collection_assistant.db.models import Base


def get_engine():
    settings = get_settings()
    url = settings.database_url
    if url.startswith("sqlite:///"):
        import os
        db_path = url.replace("sqlite:///", "")
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    return create_engine(
        url,
        connect_args={"check_same_thread": False} if "sqlite" in url else {},
    )


@lru_cache(maxsize=1)
def _get_session_factory() -> sessionmaker:
    """Build session factory once — thread-safe singleton (C-4 fix)."""
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


def create_all_tables() -> None:
    Base.metadata.create_all(get_engine())


def get_session() -> Session:
    return _get_session_factory()()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
