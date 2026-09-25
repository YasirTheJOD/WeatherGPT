"""Idempotent database initializer.

Run:  python -m app.scripts.init_db   (from backend/)

Creates tables, enables PostGIS, adds geometry columns + spatial indexes,
seeds cities from the curated seed file, seeds the source registry, and
syncs stations from the station index snapshot. Safe to run repeatedly.
"""

import asyncio
import json
import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.db.models import City, QueryLog, SourceRegistryRow, StationRow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("init_db")

SOURCES = [
    {
        "source_id": "imd",
        "name": "India Meteorological Department (IMD)",
        "status": "requires_authorization",
        "notes": "API key + IP whitelisting pending — see docs/IMD-ACCESS.md",
    },
    {"source_id": "open-meteo", "name": "Open-Meteo (GFS-derived)", "status": "verified", "notes": "Fallback + geocoding layer"},
    {"source_id": "sachet", "name": "SACHET — NDMA National Disaster Alert Portal", "status": "verified", "notes": "CAP feed with ETag caching"},
]


async def _ensure_postgis_and_geometry(engine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        for table in ("cities", "stations"):
            await conn.execute(
                text(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326)"
                )
            )
            await conn.execute(
                text(
                    f"UPDATE {table} SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) "
                    f"WHERE geom IS NULL"
                )
            )
            await conn.execute(
                text(f"CREATE INDEX IF NOT EXISTS idx_{table}_geom ON {table} USING GIST (geom)")
            )
    logger.info("postgis extension + geometry columns ensured")


async def _seed_cities(engine, seed_path: Path) -> int:
    if not seed_path.exists():
        logger.warning("cities seed file not found: %s", seed_path)
        return 0
    records = json.loads(seed_path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        logger.warning("cities seed file has unexpected shape; skipping")
        return 0

    inserted = 0
    async with engine.begin() as conn:
        existing = {
            row[0]
            for row in (
                await conn.execute(text("SELECT name FROM cities"))
            ).all()
        }
        for record in records:
            name = record.get("name")
            if not name or name in existing:
                continue
            await conn.execute(
                text(
                    "INSERT INTO cities (name, aliases, state, country_code, latitude, longitude) "
                    "VALUES (:name, :aliases, :state, :country_code, :latitude, :longitude)"
                ),
                {
                    "name": name,
                    "aliases": json.dumps(record.get("aliases", [])),
                    "state": record.get("state"),
                    "country_code": record.get("country_code", "IN"),
                    "latitude": record["latitude"],
                    "longitude": record["longitude"],
                },
            )
            inserted += 1
            existing.add(name)
    logger.info("cities seeded: %d inserted", inserted)
    return inserted


async def _seed_sources(engine) -> None:
    async with engine.begin() as conn:
        for source in SOURCES:
            await conn.execute(
                text(
                    "INSERT INTO source_registry (source_id, name, status, notes) "
                    "VALUES (:source_id, :name, :status, :notes) "
                    "ON CONFLICT (source_id) DO NOTHING"
                ),
                source,
            )
    logger.info("source registry seeded")


async def _sync_stations(engine, snapshot_path: Path) -> int:
    if not snapshot_path.exists():
        logger.info("no station snapshot at %s; stations table left as-is", snapshot_path)
        return 0
    stations = json.loads(snapshot_path.read_text(encoding="utf-8")).get("stations", [])
    synced = 0
    async with engine.begin() as conn:
        for station in stations:
            await conn.execute(
                text(
                    "INSERT INTO stations (station_code, name, state, latitude, longitude) "
                    "VALUES (:station_code, :name, :state, :latitude, :longitude) "
                    "ON CONFLICT (station_code) DO UPDATE SET "
                    "name = EXCLUDED.name, state = EXCLUDED.state, "
                    "latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude"
                ),
                {
                    "station_code": station["Station_Code"],
                    "name": station["Station_Name"],
                    "state": station.get("State"),
                    "latitude": station["Latitude"],
                    "longitude": station["Longitude"],
                },
            )
            synced += 1
    logger.info("stations synced from snapshot: %d (SAMPLE data — see backend/data/README.md)", synced)
    return synced


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, connect_args={"timeout": 5})

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        logger.error("database unavailable — is Postgres running? (%s)", exc)
        raise SystemExit(1) from exc

    await _ensure_postgis_and_geometry(engine)
    await _seed_cities(engine, Path(settings.cities_seed_path))
    await _seed_sources(engine)
    await _sync_stations(engine, Path(settings.station_snapshot_path))

    # Imported for side-effect-free schema creation completeness (unused here).
    _ = (QueryLog,)
    await engine.dispose()
    logger.info("init_db complete")


if __name__ == "__main__":
    asyncio.run(main())