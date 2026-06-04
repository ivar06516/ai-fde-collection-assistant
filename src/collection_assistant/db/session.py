from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from collection_assistant.config import get_settings
from collection_assistant.db.models import Base


def get_engine():
    settings = get_settings()
    url = settings.database_url
    # Ensure directory exists for SQLite
    if url.startswith("sqlite:///"):
        import os
        db_path = url.replace("sqlite:///", "")
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    return create_engine(url, connect_args={"check_same_thread": False} if "sqlite" in url else {})


def create_all_tables() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=None)


def get_session() -> Session:
    engine = get_engine()
    SessionLocal.configure(bind=engine)
    return SessionLocal()


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
