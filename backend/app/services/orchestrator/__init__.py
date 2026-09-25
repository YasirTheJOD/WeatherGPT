"""Orchestrator — QuerySpec → retrieval plan → EvidenceBundle.

Implemented (Phase 5): `ChatOrchestrator` in `orchestrator.py`. Owns the
location-resolution loop (explicit pick → current location → forward search →
disambiguation), the intent→provider fetch plan through the shared registry,
and the data-gap bookkeeping that keeps answers honest.
"""

from app.services.orchestrator.orchestrator import ChatOrchestrator, ChatOutcome

__all__ = ["ChatOrchestrator", "ChatOutcome"]