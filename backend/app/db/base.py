"""Async engine + session factory with a lazy, cached availability probe.

The database is optional for the prototype: `available()` returns False
without raising when Postgres is unreachable, and callers degrade gracefully
(e.g. the resolver uses the in-memory alias index, the query logger skips).
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class Database:
    _engine = None
    _session_factory: async_sessionmaker[AsyncSession] | None = None
    _available: bool | None = None

    @classmethod
    def engine(cls):
        if cls._engine is None:
            cls._engine = create_async_engine(
                get_settings().database_url,
                pool_pre_ping=True,
                connect_args={"timeout": 5},
            )
        return cls._engine

    @classmethod
    def sessions(cls) -> async_sessionmaker[AsyncSession]:
        if cls._session_factory is None:
            cls._session_factory = async_sessionmaker(cls.engine(), expire_on_commit=False)
        return cls._session_factory

    @classmethod
    async def available(cls) -> bool:
        if cls._available is None:
            try:
                async with cls.engine().connect() as conn:
                    await conn.execute(text("SELECT 1"))
                cls._available = True
                logger.info("database reachable")
            except Exception as exc:
                cls._available = False
                logger.warning("database unreachable (failing open): %s", exc)
        return cls._available