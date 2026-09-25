"""Alerts endpoints — SACHET/NDMA CAP feed (official warnings).

Alerts are authoritative government data: they are passed through as-is with
provenance; no LLM and no transformation touches the severity/urgency levels.
"""

from fastapi import APIRouter, HTTPException, Query, Request

from app.providers.base import ProviderUnavailable

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
async def nearby_alerts(
    request: Request,
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    radius_km: int = Query(default=20, ge=1, le=200),
) -> dict:
    """Official alerts near a location (uses SACHET's own location query)."""
    provider = request.app.state.alerts
    try:
        alerts = await provider.fetch_nearby(lat, lon, radius_km)
    except ProviderUnavailable as exc:
        raise HTTPException(
            status_code=503, detail={"message": str(exc)}
        ) from exc
    return {
        "alerts": [a.model_dump(mode="json") for a in alerts],
        "source": provider.provider_id,
    }


@router.get("/feed")
async def all_india_feed(request: Request) -> dict:
    """All-India CAP feed index with ETag-based caching (304 = unchanged)."""
    provider = request.app.state.alerts
    etag = getattr(request.app.state, "sachet_etag", None)
    try:
        result = await provider.fetch_feed(etag=etag)
    except ProviderUnavailable as exc:
        raise HTTPException(
            status_code=503, detail={"message": str(exc)}
        ) from exc
    request.app.state.sachet_etag = result.etag
    return {
        "modified": result.modified,
        "etag": result.etag,
        "alert_count": len(result.alerts),
        "alerts": [a.model_dump(mode="json") for a in result.alerts],
        "source": provider.provider_id,
    }