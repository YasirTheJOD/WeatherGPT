"""Location endpoints — search (with ambiguity flag), reverse, nearest station.

The `ambiguous` flag drives the Phase 4 clarifying-question loop: when a
query resolves to several close-confidence candidates, the chat asks the
user to pick instead of guessing.
"""

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("/search")
async def search_locations(
    request: Request,
    q: str = Query(min_length=2, max_length=100),
    limit: int = Query(default=8, ge=1, le=20),
) -> dict:
    result = await request.app.state.location_resolver.search(q, limit=limit)
    return result.model_dump(mode="json")


@router.get("/reverse")
async def reverse_geocode(
    request: Request,
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
) -> dict:
    candidate = await request.app.state.location_resolver.reverse(lat, lon)
    if candidate is None:
        raise HTTPException(
            status_code=404, detail={"message": "No known location near those coordinates."}
        )
    return candidate.model_dump(mode="json")


@router.get("/nearest-station")
async def nearest_station(
    request: Request,
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
) -> dict:
    candidate = request.app.state.location_resolver.nearest_station(lat, lon)
    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail={"message": "No IMD station within range."},
        )
    return candidate.model_dump(mode="json")