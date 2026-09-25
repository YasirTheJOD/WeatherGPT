"""IMD station mapping ingestion (cityforecast_mapping) -> StationIndex.

Live fetch requires the IMD API key. Until access is granted, the index is
built from an explicitly-labelled SAMPLE snapshot so the station-resolution
code path is exercised end-to-end; replace `data/stations_sample.json` with a
real capture as soon as possible (see docs/IMD-ACCESS.md).
"""

import json
import logging
from pathlib import Path

import httpx

from app.core.config import Settings
from app.domain.models import Station
from app.providers.base import ProviderUnavailable
from app.services.location.station_index import StationIndex

logger = logging.getLogger(__name__)


def _pick(record: dict, *keys: str) -> object:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def parse_mapping(data: object) -> list[Station]:
    """Tolerant parse of the mapping response.

    Expected shape: a list of records with Station_Code / Station_Name /
    Latitude / Longitude / State (IMD snake-case convention from the API
    reference). Variant key names are tolerated. Records without usable
    coordinates are skipped — a station without a location cannot serve
    nearest-station resolution.
    """
    if isinstance(data, dict) and isinstance(data.get("stations"), list):
        records = data["stations"]
    else:
        records = data
    if not isinstance(records, list):
        raise ProviderUnavailable(f"Unexpected mapping shape: {type(data).__name__}")

    stations: list[Station] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        code = _pick(record, "Station_Code", "station_code", "StationCode", "id")
        name = _pick(record, "Station_Name", "station_name", "StationName", "city", "name")
        state = _pick(record, "State", "state", "st")
        latitude = _to_float(_pick(record, "Latitude", "latitude", "lat"))
        longitude = _to_float(_pick(record, "Longitude", "longitude", "lon", "lng"))
        if not code or not name or latitude is None or longitude is None:
            logger.warning("mapping record skipped (missing fields): %s", record)
            continue
        stations.append(
            Station(
                station_code=str(code),
                name=str(name),
                state=str(state) if state else None,
                latitude=latitude,
                longitude=longitude,
            )
        )
    return stations


class IMDMappingLoader:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self._settings = settings
        self._client = client or httpx.AsyncClient(
            base_url=settings.imd_base_url, timeout=15.0
        )

    async def fetch_mapping(self) -> list[Station]:
        if not self._settings.imd_configured:
            raise ProviderUnavailable("IMD API key not configured (see docs/IMD-ACCESS.md)")
        try:
            resp = await self._client.get(
                "/api/v1/cityforecast_mapping",
                headers={"X-API-Key": self._settings.imd_api_key},
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderUnavailable(f"IMD mapping fetch failed: {exc}") from exc
        return parse_mapping(data)

    @staticmethod
    def load_snapshot(path: str | Path) -> list[Station]:
        snapshot = Path(path)
        if not snapshot.exists():
            logger.warning("station snapshot not found: %s", snapshot)
            return []
        return parse_mapping(json.loads(snapshot.read_text(encoding="utf-8")))

    async def build_index(self, snapshot_path: str | Path | None = None) -> StationIndex:
        """Live mapping first (when keyed), snapshot as fallback, empty last."""
        stations: list[Station] = []
        if self._settings.imd_configured:
            try:
                stations = await self.fetch_mapping()
            except ProviderUnavailable as exc:
                logger.warning("live mapping unavailable (%s); falling back to snapshot", exc)
        if not stations and snapshot_path:
            stations = self.load_snapshot(snapshot_path)
            if stations:
                logger.warning(
                    "STATION INDEX: built from snapshot data (sample or last-known). "
                    "Replace with a live cityforecast_mapping capture for real data."
                )
        return StationIndex(stations)