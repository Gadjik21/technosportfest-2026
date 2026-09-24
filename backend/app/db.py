from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with get_sessionmaker()() as session:
        yield session
