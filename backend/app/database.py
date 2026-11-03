from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .settings import settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str):
    connection_options = {"check_same_thread": False} if url.startswith("sqlite") else {"connect_timeout": 10}
    engine = create_engine(
        url, pool_pre_ping=True,
        connect_args=connection_options,
    )
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    return engine


engine = make_engine(settings().database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
