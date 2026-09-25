"""Source transparency endpoint — what backs every answer (ARCHITECTURE §5).

Serves the curated registry from docs/DATA-SOURCES.md with live availability,
so the demo can answer "where did that number come from?" without hand-waving
and the UI can flag official sources as official.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from app.services.sources import build_sources_report

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("")
async def list_sources(request: Request) -> dict:
    settings = request.app.state.settings
    sources = build_sources_report(settings)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "total": len(sources),
            "available": sum(1 for s in sources if s.available),
            "official": sum(1 for s in sources if s.official),
        },
        "sources": [s.model_dump(mode="json") for s in sources],
    }
