"""Health endpoints — provider availability reporting for ops and the demo."""

from fastapi import APIRouter, Request

from app import __version__

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict:
    registry = request.app.state.registry
    return {
        "status": "ok",
        "version": __version__,
        "providers": [s.model_dump(mode="json") for s in registry.statuses()],
    }