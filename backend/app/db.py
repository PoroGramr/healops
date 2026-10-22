from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.settings import settings


class Base(DeclarativeBase):
    pass


@lru_cache
def engine_for(url: str):
    return create_engine(
        url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {}
    )


def get_session() -> Iterator[Session]:
    with sessionmaker(engine_for(settings.healops_db_url))() as session:
        yield session
