# WeatherGPT

**Conversational AI for Weather Forecasting, Alerts & Climate Information** — Smart India Hackathon 2026 prototype.

Team: United India · Organization: IMD / Ministry of Earth Sciences · Theme: Disaster Management

> Meteorological systems provide the evidence; the AI explains it. **LLM ≠ Forecast Model.**

## Status labels used in this repo

`Implemented` · `Prototype` · `Planned` · `Requires authorization` · `Future scope` — nothing is presented as more than it is.

## Repository layout

```
backend/     FastAPI service — provider interfaces (IMD + Open-Meteo), typed payloads with
             provenance, provider chain with fallback, chat orchestrator + SSE,
             /health and /sources transparency, request IDs and fail-open rate limiting.
frontend/    Flutter web PWA — shell, typed API client, weather/forecast cards, alerts,
             map, streamed chat (SSE), voice, language selection, sources drawer.
infra/       docker-compose stack: backend + PostgreSQL/PostGIS + Redis, plus an optional
             nginx `web` profile (Flutter PWA + same-origin /api reverse proxy) + nginx.conf
render.yaml  Render Blueprint — one free service serves the API *and* the PWA (permanent URL)
scripts/     build_web.sh — the release recipe for the committed web bundle
.github/     keepalive.yml — keeps the free instance awake

docs/        ARCHITECTURE.md (Phase 1 baseline) · DATA-SOURCES.md (verified integration matrix)
             IMD-ACCESS.md (key + whitelist checklist) · ADRs.md (decision records)
             DEPLOYMENT.md (Phase 7 runbook: compose, env wiring, prod notes, troubleshooting)
             DEMO.md (Phase 8 SIH script: run sheet, failure drills, Q&A prep)

## Active phase

Phases follow the project brief (the P-numbers in `docs/ARCHITECTURE.md` are internal
build-order labels):

- ✅ **Phase 1** Architecture · ✅ **Phase 2** Data integration · ✅ **Phase 3** Backend core
- ✅ **Phase 4** Frontend — chat UI, location, weather cards, forecast, alerts, map, voice, languages, sources
- ✅ **Phase 5** Intelligence — query understanding, orchestrator, LLM (deterministic fallback + adapters), provenance firewall, answers rendered as they stream (`delta` → draft bubble → `done` commits the cards)
- ✅ **Phase 6** Hardening — request IDs + structured JSON logs, Redis rate limiting (fail-open),
  `/sources` transparency registry, adversarial/hallucination test matrix
- ✅ **Phase 7** Deployment — compose stack (api + PostGIS + Redis, optional nginx web profile),
  `.env` wiring, healthchecks, runbook ([`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md))
- ✅ **Phase 8** SIH demo — rehearsable demo script ([`docs/DEMO.md`](docs/DEMO.md)) driven by
  `python -m app.scripts.demo_smoke`, which gates the pre-demo checklist and rehearses the
  LLM-outage and provider-outage drills
```

## Quickstart

### Backend

```bash
cp .env.example .env          # fill IMD_API_KEY when granted (see docs/IMD-ACCESS.md)
# Option A — Docker (recommended, runs PostGIS + Redis; see docs/DEPLOYMENT.md)
docker compose -f infra/docker-compose.yml up --build -d
# Option B — local Python 3.12+ (Postgres/Redis optional — app fails open)
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m app.scripts.init_db  # schema + PostGIS geometry + seeds (skip if no DB)
uvicorn app.main:app --reload
```

Then: API docs at `http://localhost:8000/docs`, health at `/api/v1/health`, and the data-source
registry at `/api/v1/sources`. The app runs fine without Postgres and Redis — those layers fail
open (including rate limiting: with no Redis reachable no request is ever rejected).

### Frontend (Flutter web PWA)

```bash
cd frontend
flutter run -d chrome --web-port=5173   # 5173 is in the backend CORS allowlist
```

To serve the PWA and the API as **one origin on one port** (LAN, a tunnel, or a free host
that only gives you a single service), build with an empty API base URL and let the backend
serve the bundle — nothing is baked into the build, so the same artefact works anywhere:

```bash
cd frontend && flutter build web --release --dart-define=API_BASE_URL= && cd ..
cd backend  && WEB_DIR=../frontend/build/web .venv/Scripts/python -m uvicorn app.main:app --port 8000
# http://localhost:8000 -> the PWA    /api/v1/... -> the API    /docs -> API docs
```

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) §4b.

### Deployment (public URL, no Docker — Render free plan)

The repo is ready to publish as a permanent public URL on Render's free plan (no credit
card): one service serves the API and the PWA on one origin (`render.yaml`), the PWA bundle
is committed so the host never runs Flutter, and a scheduled workflow keeps the free
instance awake. Runbook: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) §9.

> The repository half is verified (the bundle boots in a browser and calls the API
> same-origin; the service's exact start command passed `demo_smoke` 8/8 locally), but no
> real Render deploy has been run yet — that needs an account and a push.

### Deployment (full stack, Docker)

The compose file also carries an optional `web` profile: nginx serves the built Flutter
PWA and reverse-proxies `/api` on the same origin, so the browser needs no CORS.

```bash
cd frontend && flutter build web --release --dart-define=API_BASE_URL=http://localhost:8080 && cd ..
docker compose -f infra/docker-compose.yml --profile web up --build -d   # app at http://localhost:8080
```

Services and ports, `.env` wiring, operational commands, production notes (TLS, workers,
rate limiting behind a proxy) and troubleshooting: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

> **Not yet verified:** the compose stack was authored and syntax-checked, but no live
> `docker compose up` has been run — the development environment has no Docker. Every
> rehearsal so far went through a local `uvicorn`. Treat the container path as reviewed,
> not proven, until `demo_smoke` passes against it.

### Tests

```bash
cd backend
pytest                     # hermetic — fixture-based, no network
RUN_LIVE_TESTS=1 pytest    # additionally runs live Open-Meteo tests
```

Demo rehearsal (needs a running API, exits non-zero on any failure — it is the pre-demo
gate). Full script, run sheet and drills: [`docs/DEMO.md`](docs/DEMO.md).

```bash
cd backend && python -m app.scripts.demo_smoke --base-url http://localhost:8000   # 8/8 in ~20s
```

### Hardening (Phase 6)

- **Request IDs & structured logs.** Every response carries `X-Request-ID` (an incoming
  value is echoed, otherwise one is minted) and every log line is a JSON object stamped
  with it. The streaming `/chat` endpoint is unaffected (raw ASGI middleware, no buffering).
- **Rate limiting.** Redis fixed window per client IP across `/api/v1` (health exempted),
  tuned by `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW_SECONDS`. It **fails open**: with no
  Redis reachable, or on any Redis error, requests are never rejected.
- **Source transparency.** `GET /api/v1/sources` serves the curated integration matrix
  from `docs/DATA-SOURCES.md` with live availability, and the in-app sources drawer reads
  it (localized descriptions keyed by source id, official flag, curated status vs. live
  availability). If the registry is unreachable the drawer shows an explicit error banner
  with a Retry action, above the built-in list. The registry is fetched **once** by a shared
  `SourcesController`; the alerts and map tabs also show a compact strip of the sources
  backing them (SACHET/IMD, OSM/SACHET) with the same live status.
- **Adversarial / hallucination matrix.** `backend/tests/test_adversarial_*.py` pin the
  safety guarantees: a lying LLM can change the prose but never the cards, the number
  firewall reports every invented value, wrong/ambiguous places are asked about rather
  than answered, prompt-injection text cannot dictate data, Devanagari/Hinglish parse
  correctly, and stale or corrupt provider data is surfaced (or discarded) — never
  silently presented as fresh.
- **Multilingual place resolution.** Devanagari city names (`दिल्ली`, `कोलकाता`, `मुंबई`, …)
  resolve through the curated offline alias index, because the geocoder can only be searched
  in Latin script. The index is guarded against normalized-alias collisions (two names
  folding onto one city would silently answer about the wrong place), and the rehearsal
  harness gates the Devanagari path end-to-end. The UI is localized with it: the location
  quick picks render in Devanagari under the Hindi locale while still searching the
  canonical Latin name (the geocoder is Latin-only, so the label must never be the query).

## Verified data sources (2026-09-06)

| Source | Status | Role |
|--------|--------|------|
| IMD `api.imd.gov.in` | Requires authorization (API key; IP whitelist per IMD docs) | Primary authoritative obs/forecast/warnings |
| Open-Meteo | Prototype — free, keyless | Fallback + geocoding (GFS-derived) |
| SACHET CAP feed | Prototype — **live-verified** (RSS index + CAP detail + location alerts, ETag caching) | Secondary official warnings |
| MOSDAC / GFS raw | Requires authorization / Planned | Future scope |

Full evidence-backed matrix: [`docs/DATA-SOURCES.md`](docs/DATA-SOURCES.md).

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — Phase 1 baseline: MVP scope, system design, API boundaries, schema, AI orchestration, security, dev order, demo scenarios
- [`docs/DATA-SOURCES.md`](docs/DATA-SOURCES.md) — verified integration matrix with evidence links
- [`docs/IMD-ACCESS.md`](docs/IMD-ACCESS.md) — IMD API key + whitelist application checklist
- [`docs/ADRs.md`](docs/ADRs.md) — architecture decision records
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — Phase 7 runbook: services and ports, `.env` wiring, operational commands, production notes, troubleshooting
- [`docs/DEMO.md`](docs/DEMO.md) — Phase 8 SIH demo script: pre-flight checklist, 8-minute run sheet, failure drills, Q&A prep, recovery table