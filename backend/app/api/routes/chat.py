"""POST /chat — SSE-streamed grounded answers.

Event protocol (each event: `event: <name>` + `data: <json>` + blank line):

  meta  — pipeline progress (`status`: resolving → fetching → generating),
          the detected intent, and the resolved location when known.
  delta — partial answer text, word-chunked so the frontend renders it
          progressively as it arrives; `done` still carries the complete
          answer, so a client may ignore deltas and use `done` alone.
  done  — the full ChatResponse payload: text + cards (observation/forecast/
          alerts) + location/candidates + suggestions + source + provenance
          check. Exactly the shape the Flutter ChatReply mapper consumes.
  error — fatal message; the stream ends without `done` (frontend falls back
          to the deterministic typed endpoints).

Resilience: if the configured LLM provider fails at runtime (bad key,
outage), the deterministic template responder answers from the same evidence
bundle — identical provenance, only fluency differs. The demo never dies.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.domain.chat import ChatRequest
from app.providers.base import ProviderUnavailable
from app.providers.llm.base import LLMProvider
from app.providers.llm.fallback import FallbackLLMProvider
from app.services.response.assembler import assemble_chat_response
from app.services.response.provenance import check_provenance

router = APIRouter(prefix="/chat", tags=["chat"])

logger = logging.getLogger("app.chat")

_WORDS_PER_CHUNK = 7


def _sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _word_chunks(text: str) -> list[str]:
    words = text.split()
    return [
        " ".join(words[i : i + _WORDS_PER_CHUNK])
        for i in range(0, len(words), _WORDS_PER_CHUNK)
    ]


async def _grounded_text(
    llm: LLMProvider, evidence, message: str, language: str
) -> tuple[str, bool]:
    """Answer from evidence; NEVER let a provider problem kill the stream.

    Returns (text, used_fallback). ``ProviderUnavailable`` is the expected
    failure (missing key, outage, unparseable vendor response), but a provider
    bug — or a successful call that returns nothing — is treated the same way:
    the deterministic responder answers from the same evidence bundle. A blank
    chat bubble is not an acceptable demo outcome.
    """
    text = ""
    try:
        text = await llm.grounded_response(evidence, message, language=language)
    except ProviderUnavailable as exc:
        logger.warning("LLM provider unavailable, using fallback: %s", exc)
    except Exception as exc:  # noqa: BLE001 — deliberate catch-all (demo safety)
        logger.warning("LLM provider raised unexpectedly, using fallback: %s", exc)

    if not (text or "").strip():
        fallback = await FallbackLLMProvider().grounded_response(
            evidence, message, language=language
        )
        return fallback, True
    return text, False


@router.post("")
async def chat(request: Request, payload: ChatRequest) -> StreamingResponse:
    orchestrator = request.app.state.chat_orchestrator

    async def event_stream():
        try:
            yield _sse("meta", {"status": "resolving", "intent": payload.intent})
            if payload.candidate is not None:
                outcome = await orchestrator.run_for_candidate(
                    request,
                    payload.candidate,
                    payload.intent or "current_weather",
                    payload.language,
                    current_location=payload.current_location,
                )
            else:
                outcome = await orchestrator.run(
                    request,
                    payload.message,
                    payload.language,
                    current_location=payload.current_location,
                )
        except Exception as exc:  # defensive: never let the stream die silently
            yield _sse("error", {"message": f"Something went wrong: {exc}"})
            return

        # Conversational outcomes (ask for place / not found / disambiguation)
        # are complete without evidence or an LLM call.
        if outcome.kind in ("not_found", "needs_location", "disambiguation"):
            response = assemble_chat_response(outcome, text="")
            yield _sse("done", response.model_dump(mode="json"))
            return

        evidence = outcome.evidence
        location = (
            outcome.spec.location.model_dump(mode="json")
            if outcome.spec and outcome.spec.location
            else None
        )
        yield _sse(
            "meta",
            {
                "status": "fetching",
                "intent": outcome.spec.intent,
                "location": location,
            },
        )

        text, used_fallback = await _grounded_text(
            request.app.state.llm,
            evidence,
            payload.message,
            payload.language,
        )
        yield _sse(
            "meta",
            {
                "status": "generating",
                "fallback": used_fallback,
                "intent": outcome.spec.intent,
            },
        )
        for chunk in _word_chunks(text):
            yield _sse("delta", {"text": chunk})

        provenance = check_provenance(text, evidence)
        response = assemble_chat_response(outcome, text, provenance)
        yield _sse("done", response.model_dump(mode="json"))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )