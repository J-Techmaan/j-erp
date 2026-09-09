from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(url):
    sqlite = url.startswith('sqlite')
    engine = create_engine(url, connect_args={'check_same_thread': False, 'timeout': 15} if sqlite else {})
    if sqlite:
        @event.listens_for(engine, 'connect')
        def pragmas(connection, _):
            cursor = connection.cursor()
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.close()
    return engine


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        try:
            yield db
        except Exception:
            db.rollback()
            raise
