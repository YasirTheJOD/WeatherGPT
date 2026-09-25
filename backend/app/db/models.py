"""ORM models (Phase 3 subset).

cities/stations carry PostGIS geometry via the init script (raw DDL keeps the
ORM lean); source_registry feeds the transparency story; query_log is the
audit trail for the demo (chat-level logging lands with the orchestrator).
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    aliases: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    state: Mapped[str | None] = mapped_column(String(120))
    country_code: Mapped[str] = mapped_column(String(2), default="IN", nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)


class StationRow(Base):
    __tablename__ = "stations"

    station_code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    state: Mapped[str | None] = mapped_column(String(120))
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)


class SourceRegistryRow(Base):
    __tablename__ = "source_registry"

    source_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)  # verified | prototype | requires_authorization | planned
    notes: Mapped[str | None] = mapped_column(Text)
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QueryLog(Base):
    __tablename__ = "query_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(String(80), nullable=False)
    query_text: Mapped[str | None] = mapped_column(Text)
    provider_used: Mapped[str | None] = mapped_column(String(40))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    fallback: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )