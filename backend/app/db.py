"""数据库引擎与会话（惰性初始化：导入时不连库，用到才建引擎）。"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_settings().sqlalchemy_url, pool_pre_ping=True, pool_recycle=3600, future=True
        )
    return _engine


def get_sessionmaker() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autoflush=False, autocommit=False, future=True
        )
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每个请求一个会话。"""
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()
