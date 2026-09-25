"""Phase 8 demo rehearsal — drive the SIH demo scenarios against a running API.

The demo is a performance, so it needs a rehearsal you can run in one command.
This exercises every scenario that can be scripted (voice input and the map
gestures are manual — they are listed at the end of the report) and it can also
be pointed at a *deliberately broken* stack to rehearse the failure drills.

Usage
-----
    # Normal rehearsal: live data, deterministic responder.
    python -m app.scripts.demo_smoke --base-url http://localhost:8000

    # LLM outage drill — start the API with a broken provider:
    #   LLM_PROVIDER=groq GROQ_API_KEY= uvicorn app.main:app --port 8011
    python -m app.scripts.demo_smoke --base-url http://localhost:8011 --expect-llm-fallback

    # Weather-provider outage drill — start the API with a dead upstream:
    #   OPEN_METEO_BASE_URL=http://127.0.0.1:9 uvicorn app.main:app --port 8012
    python -m app.scripts.demo_smoke --base-url http://localhost:8012 --expect-provider-outage

Exit code is non-zero if any scripted scenario fails, so the same command can
gate the pre-demo checklist. The evaluators below are pure functions over the
parsed SSE frames, and are unit-tested in tests/test_demo_smoke.py.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass

import httpx

KOLKATA = {
    "name": "Kolkata",
    "state": "West Bengal",
    "country_code": "IN",
    "latitude": 22.57,
    "longitude": 88.36,
    "source": "demo-script",
    "confidence": 0.99,
}

MANUAL_STEPS = [
    "Scenario 4 (map): search 'Kolkata', show the pin + official alert footprints",
    "Scenario 5 (voice): tap the mic, ask in Hindi, hear the answer spoken back "
    "(the API half is scripted above — दिल्ली must resolve)",
    "Scenario 3 (alerts): scroll the OFFICIAL WARNING block and read the do's/don'ts",
    "Scenario 7 (transparency): open the sources drawer and show the live registry + IMD status",
]


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested without a server)
# ---------------------------------------------------------------------------


def parse_sse(body: str) -> list[tuple[str, dict]]:
    """`event: x` + `data: {...}` blocks -> (event, payload) pairs."""
    events: list[tuple[str, dict]] = []
    for block in body.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event = "message"
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        if data_lines:
            events.append((event, json.loads("\n".join(data_lines))))
    return events


def done_payload(events: list[tuple[str, dict]]) -> dict:
    return next((d for e, d in events if e == "done"), {})


def meta_payload(events: list[tuple[str, dict]], status: str) -> dict:
    return next(
        (d for e, d in events if e == "meta" and d.get("status") == status), {}
    )


def _has_error(events: list[tuple[str, dict]]) -> bool:
    return any(e == "error" for e, _ in events)


def _answer(events: list[tuple[str, dict]]) -> str:
    return done_payload(events).get("text", "")


def _preview(text: str, limit: int = 150) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _verified(done: dict) -> bool:
    """An *answered* response must carry a passing provenance check.

    `provenance_check` is present-but-null on the conversational outcomes
    (not found / needs place / disambiguation), so a plain `.get(k, {})` is not
    enough — None means "no data to check", which never counts as verified.
    """
    check = done.get("provenance_check") or {}
    return bool(check.get("verified"))


def evaluate_weather(
    events: list[tuple[str, dict]],
    *,
    expect_llm_fallback: bool = False,
    expect_provider_outage: bool = False,
) -> tuple[bool, str]:
    """Scenario 1: a grounded current-conditions answer (or a graceful gap)."""
    if _has_error(events):
        return False, "streamed an `error` event — the demo must degrade gracefully"
    done = done_payload(events)
    if not done:
        return False, "no `done` event"
    text = _answer(events)

    if expect_provider_outage:
        if "don't have live data" not in text:
            return False, f"expected a graceful gap answer, got: {_preview(text)}"
        if done.get("observation") is not None:
            return False, "reported an observation while the provider was down"
        return True, _preview(text)

    if not _verified(done):
        return False, (
            "no verified provenance — reply was "
            f"{_preview(text)} (check={done.get('provenance_check')})"
        )
    if done.get("intent") != "current_weather":
        return False, f"intent was {done.get('intent')!r}"
    if done.get("observation") is None:
        return False, "no observation card"
    if "Kolkata" not in text:
        return False, f"answer did not name the resolved place: {_preview(text)}"

    fallback = bool(meta_payload(events, "generating").get("fallback"))
    if fallback != expect_llm_fallback:
        return False, (
            f"LLM fallback flag was {fallback}, expected {expect_llm_fallback}"
        )
    return True, _preview(text)


def evaluate_forecast(
    events: list[tuple[str, dict]],
    *,
    expect_llm_fallback: bool = False,
    expect_provider_outage: bool = False,
) -> tuple[bool, str]:
    """Scenario 2: Hinglish query grounded on the right day."""
    done = done_payload(events)
    if _has_error(events) or not done:
        return False, "no usable answer"
    text = _answer(events)

    if expect_provider_outage:
        return (
            ("don't have live data" in text),
            _preview(text),
        )

    if done.get("intent") != "forecast":
        return False, f"intent was {done.get('intent')!r}"
    if not done.get("forecast"):
        return False, "no forecast card"
    if done.get("location") is None or "Mumbai" not in str(done.get("location")):
        return False, f"wrong location: {done.get('location')}"
    if "Tomorrow" not in text:
        # "कल" means tomorrow: the answer must land on day 2, not today.
        return False, f"did not resolve to tomorrow: {_preview(text)}"
    if not _verified(done):
        return False, f"provenance check failed (check={done.get('provenance_check')})"

    fallback = bool(meta_payload(events, "generating").get("fallback"))
    if fallback != expect_llm_fallback:
        return False, f"LLM fallback flag was {fallback}"
    return True, _preview(text)


def evaluate_alerts(events: list[tuple[str, dict]]) -> tuple[bool, str]:
    """Scenario 3: official warnings path, never relabelled by the app."""
    done = done_payload(events)
    if _has_error(events) or not done:
        return False, "no usable answer"
    if done.get("intent") != "alerts":
        return False, f"intent was {done.get('intent')!r}"

    text = _answer(events)
    alerts = done.get("alerts") or []
    if alerts:
        return True, f"{len(alerts)} official warning(s): {_preview(text)}"
    if "No official warnings" in text:
        return True, _preview(text)
    return False, f"expected warnings or a clear 'none' — got: {_preview(text)}"


def evaluate_not_found(events: list[tuple[str, dict]]) -> tuple[bool, str]:
    """Safety: an unknown place is refused, never invented."""
    done = done_payload(events)
    if _has_error(events) or not done:
        return False, "no usable answer"
    text = _answer(events)
    if "couldn't find a place called" not in text:
        return False, f"expected a 'not found' reply, got: {_preview(text)}"
    if done.get("observation") is not None or done.get("forecast"):
        return False, "invented data for an unknown place"
    return True, _preview(text)


def evaluate_devanagari_hindi(
    events: list[tuple[str, dict]],
    search_body: dict,
    *,
    expect_provider_outage: bool = False,
) -> tuple[bool, str]:
    """Scenario 5's API half: a Devanagari question must resolve and answer.

    The voice scenario fails silently and embarrassingly if a Devanagari place
    name does not resolve: Open-Meteo Geocoding is searched in Latin script, so
    the curated alias index is the *only* thing that can resolve "दिल्ली". The
    regression this guards is concrete — Devanagari city names were missing from
    `cities_seed.json`, so every Hindi place query came back "I couldn't find a
    place called …" while the app advertised Hindi support.
    """
    candidates = search_body.get("candidates") or []
    searched = (candidates[0].get("name") if candidates else None) or "nothing"
    if "Delhi" not in searched:
        return False, f"Devanagari search resolved to {searched!r}"

    if _has_error(events):
        return False, "chat stream errored on a Devanagari question"
    text = _answer(events)
    if "couldn't find a place called" in text:
        return False, f"Devanagari place was not resolved: {_preview(text)}"

    done = done_payload(events)
    if expect_provider_outage:
        return True, f"दिल्ली resolved; graceful gap answer: {_preview(text)}"
    if not done.get("forecast"):
        return False, f"no forecast cards: {_preview(text)}"
    if not _verified(done):
        return False, "provenance not verified"
    place = (done.get("location") or {}).get("name")
    if place and place != searched:
        # The wrong-location class of bug: the search resolved one city and the
        # answer is about another.
        return False, f"search resolved {searched!r} but the answer is for {place!r}"
    return True, f"दिल्ली → {place or searched}: {_preview(text, 90)}"


# ---------------------------------------------------------------------------
# Scenarios (network)
# ---------------------------------------------------------------------------


async def _chat(client: httpx.AsyncClient, payload: dict) -> list[tuple[str, dict]]:
    resp = await client.post("/api/v1/chat", json=payload)
    resp.raise_for_status()
    return parse_sse(resp.text)


async def _wait_for_ready(client: httpx.AsyncClient, seconds: int) -> bool:
    for _ in range(max(1, seconds * 2)):
        try:
            resp = await client.get("/api/v1/health")
            if resp.status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        await asyncio.sleep(0.5)
    return False


async def run_rehearsal(
    client: httpx.AsyncClient,
    *,
    expect_llm_fallback: bool = False,
    expect_provider_outage: bool = False,
) -> list[Check]:
    checks: list[Check] = []

    health = await client.get("/api/v1/health")
    body = health.json()
    providers = {p["provider_id"]: p["available"] for p in body.get("providers", [])}
    ok = health.status_code == 200 and body.get("status") == "ok" and providers
    request_id = health.headers.get("x-request-id", "")
    checks.append(
        Check(
            "health + request id",
            bool(ok and request_id),
            f"providers={providers} request_id={'yes' if request_id else 'MISSING'}",
        )
    )

    sources = await client.get("/api/v1/sources")
    sbody = sources.json()
    ids = {s["source_id"] for s in sbody.get("sources", [])}
    expected_ids = {"imd", "open_meteo", "sachet"}
    counts = sbody.get("counts", {})
    checks.append(
        Check(
            "source registry",
            sources.status_code == 200 and expected_ids <= ids and counts.get("total") == len(ids),
            f"ids={sorted(ids)} available={counts.get('available')}/{counts.get('total')} "
            f"official={counts.get('official')}",
        )
    )

    weather = await _chat(client, {"message": "What's the weather in Kolkata right now?"})
    ok, detail = evaluate_weather(
        weather,
        expect_llm_fallback=expect_llm_fallback,
        expect_provider_outage=expect_provider_outage,
    )
    checks.append(Check("scenario 1 · current weather (English)", ok, detail))

    forecast = await _chat(client, {"message": "Kal shaam Mumbai mein baarish hogi kya?"})
    ok, detail = evaluate_forecast(
        forecast,
        expect_llm_fallback=expect_llm_fallback,
        expect_provider_outage=expect_provider_outage,
    )
    checks.append(Check("scenario 2 · Hinglish forecast", ok, detail))

    alerts = await _chat(
        client,
        {
            "message": "Is there a heavy rain warning in my area? What should I do?",
            "current_location": KOLKATA,
        },
    )
    ok, detail = evaluate_alerts(alerts)
    checks.append(Check("scenario 3 · official warnings", ok, detail))

    search = await client.get("/api/v1/locations/search", params={"q": "kolkata"})
    candidates = search.json().get("candidates", [])
    alerts_endpoint = await client.get(
        "/api/v1/alerts", params={"lat": 22.57, "lon": 88.36, "radius_km": 20}
    )
    abody = alerts_endpoint.json()
    ok = (
        search.status_code == 200
        and candidates
        and "Kolkata" in candidates[0].get("name", "")
        and alerts_endpoint.status_code == 200
        and "alerts" in abody
    )
    checks.append(
        Check(
            "scenario 4 · location search + alert geometry (API half)",
            bool(ok),
            f"top candidate={candidates[0].get('name') if candidates else None} "
            f"alerts={len(abody.get('alerts', []))} source={abody.get('source')}",
        )
    )

    hindi_search = await client.get("/api/v1/locations/search", params={"q": "दिल्ली"})
    hindi = await _chat(client, {"message": "कल दिल्ली में बारिश होगी क्या?"})
    ok, detail = evaluate_devanagari_hindi(
        hindi,
        hindi_search.json() if hindi_search.status_code == 200 else {},
        expect_provider_outage=expect_provider_outage,
    )
    checks.append(Check("scenario 5 · Devanagari question (voice API half)", ok, detail))

    unknown = await _chat(client, {"message": "What's the weather in xyzzy-not-a-place?"})
    ok, detail = evaluate_not_found(unknown)
    checks.append(Check("safety · unknown place is not invented", ok, detail))

    return checks


def configure_console() -> None:
    """Make the report printable on consoles that are not UTF-8.

    The report is drawn with box characters and echoes real answers — degree
    signs, arrows, Devanagari place names. On Windows, Python uses the console API
    (UTF-8) only for a real console; as soon as `stdout` is a pipe or a
    redirection — `| tee rehearsal.log`, a CI step — the locale's legacy code page
    (cp1252 here) applies, and the very first `print` raised UnicodeEncodeError
    *after* every scenario had already run. The rehearsal died at the finishing
    line and reported nothing, which is the worst possible failure for the
    pre-demo gate. Ask for UTF-8, and never raise on a character the stream cannot
    represent.
    """
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:  # a non-reconfigurable stream (test double, etc.)
        return
    try:
        reconfigure(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        pass


def render(checks: list[Check], *, drills: list[str]) -> int:
    width = max(len(c.name) for c in checks) if checks else 10
    print("\n WeatherGPT demo rehearsal\n" + "─" * (width + 60))
    for check in checks:
        mark = "PASS" if check.ok else "FAIL"
        print(f" [{mark}] {check.name.ljust(width)}  {check.detail}")

    failures = [c for c in checks if not c.ok]
    print("─" * (width + 60))
    print(f" {len(checks) - len(failures)}/{len(checks)} scripted scenarios passed")

    if drills:
        print("\n Active failure drill(s): " + ", ".join(drills))

    print("\n Manual steps (not scriptable):")
    for step in MANUAL_STEPS:
        print(f"   · {step}")

    if failures:
        print("\n Something is off — fix before the demo:")
        for check in failures:
            print(f"   · {check.name}: {check.detail}")
    print()
    return 1 if failures else 0


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--expect-llm-fallback",
        action="store_true",
        help="LLM outage drill: assert the deterministic responder answered.",
    )
    parser.add_argument(
        "--expect-provider-outage",
        action="store_true",
        help="Provider outage drill: assert a graceful gap answer, not an error.",
    )
    parser.add_argument(
        "--wait-seconds",
        type=int,
        default=20,
        help="Poll /health for this long before giving up (default 20).",
    )
    args = parser.parse_args(argv)

    drills = [
        name
        for name, flag in (
            ("LLM outage", args.expect_llm_fallback),
            ("provider outage", args.expect_provider_outage),
        )
        if flag
    ]

    configure_console()
    async with httpx.AsyncClient(base_url=args.base_url, timeout=30.0) as client:
        print(f" Rehearsing against {args.base_url} …")
        if not await _wait_for_ready(client, args.wait_seconds):
            print(f"\n API never became healthy at {args.base_url}.")
            print(" Start the stack (see docs/DEPLOYMENT.md) and try again.\n")
            return 1
        checks = await run_rehearsal(
            client,
            expect_llm_fallback=args.expect_llm_fallback,
            expect_provider_outage=args.expect_provider_outage,
        )
    return render(checks, drills=drills)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
