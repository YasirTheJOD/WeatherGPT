"""Typed weather endpoints — the provider-chain smoke test for the scaffold.

Full chat/orchestrator flows land in Phase 4-6; these typed endpoints exist
so the frontend can render weather cards directly and so the provider
interfaces can be verified end-to-end.
"""

from fastapi import APIRouter, HTTPException, Query, Request

from app.providers.base import LocationQuery, ProviderUnavailable

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/current")
async def current_weather(
    request: Request,
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    station_id: str | None = None,
    city: str | None = None,
) -> dict:
    location = LocationQuery(
        latitude=lat, longitude=lon, station_id=station_id, city_name=city
    )
    try:
        observation, provider_id, validation = await request.app.state.registry.current_weather(
            location
        )
    except ProviderUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"message": str(exc), "hint": "Check /api/v1/health for provider status."},
        ) from exc
    return {
        "observation": observation.model_dump(mode="json"),
        "provider_used": provider_id,
        "validation": validation.model_dump(mode="json"),
    }


@router.get("/forecast")
async def daily_forecast(
    request: Request,
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    days: int = Query(default=7, ge=1, le=7),
    station_id: str | None = None,
    city: str | None = None,
) -> dict:
    location = LocationQuery(
        latitude=lat, longitude=lon, station_id=station_id, city_name=city
    )
    try:
        forecast, provider_id, validation = await request.app.state.registry.daily_forecast(
            location, days=days
        )
    except ProviderUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"message": str(exc), "hint": "Check /api/v1/health for provider status."},
        ) from exc
    return {
        "forecast": [day.model_dump(mode="json") for day in forecast],
        "provider_used": provider_id,
        "validation": validation.model_dump(mode="json"),
    }