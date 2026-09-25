# WeatherGPT — Phase 1 Architecture Baseline

> Project: WeatherGPT (Conversational AI for Weather Forecasting, Alerts & Climate Information)
> Team: United India | Organization: IMD / MoES | Theme: Disaster Management | SIH 2026
> Document status: **Baseline v1** (Phase 1, Step 1). Author: Lead Solution Architect.
> Verified as of: 2026-09-06. Every external integration claim below is backed by a check performed on this date; see `docs/DATA-SOURCES.md` for evidence links.

---

## 0. North Star & Non-Negotiables

- **LLM ≠ Forecast Model.** Meteorological systems provide the evidence; the LLM explains it. The system must never fabricate observations, forecasts, warnings, or certainty.
- **Official warnings are authoritative and never overridden or re-labelled.** AI-generated interpretation is always visually and textually distinguishable from official information.
- **Every answer carries provenance:** which source, fetched at what time, what data type, what confidence.
- **Demo reliability is a feature:** if the LLM or a data API fails mid-demonstration, the system still answers with grounded, templated responses.
- **API-first and modular:** LLM provider, weather provider, speech provider, map provider, and cache/DB are replaceable without rewriting the application.

---

## 1. Critical Review of the Original Concept

What is sound, what is risky, and what must change before we build.

| # | Finding | Severity | Resolution |
|---|---------|----------|------------|
| 1 | The concept assumes "IMD API" exists as a pluggable free source. It does exist — but access is gated by **IP whitelisting** (IMD requires the caller's public IP to be whitelisted; no API key). | High | Apply for whitelisting early (IMD is the SIH nodal — use the problem-statement channel). Until granted, run on the Open-Meteo fallback behind the same provider interface. |
| 2 | "RAG" is mis-scoped in the proposal. Weather data is retrieved from APIs, not documents. RAG only applies to a **knowledge base of advisories** (IMD do's/don'ts, glossaries, FAQ). | Medium | MVP uses a small, human-curated advisory KB (JSON, no vector DB). Vector retrieval = planned, not required. |
| 3 | "NWP models such as GFS/WRF" in the proposal is a scope trap. Running/ingesting WRF or raw GRIB is a project of its own. | High | Out of MVP. GFS-derived point forecasts are already served by Open-Meteo; raw GFS (AWS Open Data / NOMADS) is a **future** map-layer capability. |
| 4 | MOSDAC is not a chat-friendly REST API. Verified: it is a **bulk satellite-data download tool** (Python script + config, username/password account, approval required, 5,000 files/day cap). | Medium | Relegate to **future** (satellite imagery layer / cyclone demo). Not needed for MVP core. |
| 5 | Location ambiguity is underestimated. India has many duplicate place names (e.g., multiple "Ranipur"/"Kota"); Hinglish spellings vary. | Medium | Curated alias dictionary + geocoding + explicit disambiguation question in chat when confidence is low. |
| 6 | Multi-source "data fusion / conflict handling" as proposed is over-engineered for MVP and can produce confusion. | Medium | MVP: **one authoritative source per parameter** (IMD primary, Open-Meteo fallback), with freshness + plausibility validation. Cross-source comparison = planned. |
| 7 | "Risk & impact analysis" risks inventing severity. | High | Severity never comes from the LLM. A **static, human-reviewed lookup table** maps official IMD warning codes/colors → hazard category → plain-language guidance. |
| 8 | Broad multilingual + voice + map scope can sink the schedule if sequenced wrong. | Medium | Text-first chat is the demo core. Voice (browser STT/TTS, zero API keys), Hindi + 1–2 more languages, and map are added after core is stable. |
| 9 | "Kubernetes-ready" vs "don't overengineer" contradiction. | Low | Docker Compose for the SIH prototype. Stateless services + env-driven config so K8s migration is a config change, not a rewrite. |
| 10 | LLM hallucination + prompt injection are real threats in a chat product. | High | Evidence-bundle-only prompting, tool-call allowlist, **number-provenance post-check** (every number in the answer must exist in the fetched evidence), and official/AI labeling. |
| 11 | Stale data and API downtime are not addressed in the proposal. | Medium | Per-datatype TTLs, "as of" timestamps on every response, graceful "data unavailable" language, max 1 retry per fetch. |
| 12 | Weather-forecast accuracy is not our claim to make. | Medium | We relay IMD/GFS values with attribution. We never state or imply our own forecast accuracy. |

**Verdict:** the architecture direction is sound and the differentiator (conversational intelligence on authoritative infrastructure) is real. The changes above convert it into something buildable and demonstrable in hackathon time.

---

## 2. Final MVP Scope (SIH Demonstration)

### IN (demonstrable at SIH)

1. **Conversational weather query** — "What's the weather in Kolkata right now?" → temperature, condition, humidity, wind, rain, plus timestamp & source. Only parameters actually available from the connected source are shown.
2. **Forecast query** — "Will it rain tomorrow evening?" → natural-language explanation grounded in the forecast payload, with the requested time window.
3. **Location awareness** — current location (browser geolocation), typed city search, and lat/lon input; ambiguity handled with a clarifying question.
4. **Alert awareness** — official district warnings (IMD) rendered as an **OFFICIAL WARNING** block, then explained in plain language with do's/don'ts from the advisory KB.
5. **Multilingual** — English + Hindi + Hinglish chat; architecture open for more languages.
6. **Voice** — browser Speech-to-Text → WeatherGPT → Text-to-Speech (zero external API keys; cloud providers behind an interface for later).
7. **Map** — location pin + alert markers (district level) on an OSM-based map.
8. **Source transparency** — every response carries a source card (source, timestamp, data type).
9. **Deterministic fallback mode** — grounded templated answers when the LLM provider is unreachable. Demo never dies.
10. **Safety separations** — OFFICIAL WARNING blocks vs. AI interpretation; no invented numbers (provenance check).

### OUT (labelled — planned / future / requires authorization)

| Item | Label |
|------|-------|
| MOSDAC satellite data & imagery layers | Requires authorization; future |
| NDMA/SACHET deep integration (beyond CAP feed ingest) | Requires authorization; future |
| Raw GFS/WRF ingestion, model-run maps | Future |
| RAG over large document corpus / vector DB | Planned (post-MVP) |
| Multi-source conflict fusion UI | Planned (post-MVP) |
| User accounts, auth, personalization | Future |
| WebSocket live alert push, MQTT | Future |
| Native Android/iOS apps | Future (Flutter codebase supports it) |
| Cloud STT/TTS providers | Future (interface ready) |
| PostGIS-heavy analytics (radius alert queries at scale) | Future (simple Python geometry for MVP) |

---

## 3. System Architecture

```
                        ┌─────────────────────────────────────────────────────┐
                        │  FRONTEND — Flutter Web PWA (mobile-first, later    │
                        │  Android/iOS from same codebase)                    │
                        │  Chat · Location bar · Weather card · Forecast      │
                        │  strip · Alert banner · Map (flutter_map/OSM) ·     │
                        │  Language selector · Source drawer · Voice (Web     │
                        │  Speech API via JS bridge)                          │
                        └──────────────────────┬──────────────────────────────┘
                                               │ HTTPS + SSE (token streaming)
                        ┌──────────────────────▼──────────────────────────────┐
                        │  BACKEND — FastAPI (Docker)                         │
                        │  API layer: /chat /weather /locations /alerts       │
                        │             /sources /health                        │
                        │  ┌───────────────────────────────────────────────┐  │
                        │  │ 1. QUERY UNDERSTANDING                        │  │
                        │  │   intent · location · date/time · language    │  │
                        │  │   parameter · alert-needed · advisory-needed  │  │
                        │  │   (rules first; LLM assist for Hinglish)      │  │
                        │  ├───────────────────────────────────────────────┤  │
                        │  │ 2. ORCHESTRATOR                               │  │
                        │  │   retrieval plan → choose providers/tools      │  │
                        │  │   parallel fetch · disambiguation loop         │  │
                        │  ├───────────────────────────────────────────────┤  │
                        │  │ 3. TOOL/PROVIDER LAYER (uniform interface)    │  │
                        │  │   IMD · Open-Meteo · SACHET CAP · Geocoder    │  │
                        │  │   Advisory KB · LLM (OpenAI/Gemini/Groq/...)   │  │
                        │  ├───────────────────────────────────────────────┤  │
                        │  │ 4. VALIDATION & NORMALIZATION                 │  │
                        │  │   schema check · plausibility · freshness      │  │
                        │  │   units · source rank · provenance envelope    │  │
                        │  ├───────────────────────────────────────────────┤  │
                        │  │ 5. RISK / IMPACT (lookup-table only)          │  │
                        │  │   warning color/code → hazard → impact → action│  │
                        │  ├───────────────────────────────────────────────┤  │
                        │  │ 6. GROUNDED LLM RESPONSE                      │  │
                        │  │   evidence-bundle prompt · tool calling ·      │  │
                        │  │   structured output · provenance check ·       │  │
                        │  │   official-vs-AI labeling · fallback mode       │  │
                        │  └───────────────────────────────────────────────┘  │
                        └───────┬──────────────────────────┬─────────────────┘
                                │                          │
                    ┌───────────▼──────────┐   ┌───────────▼──────────┐
                    │ PostgreSQL + PostGIS │   │ Redis (cache, rate   │
                    │ cities/stations,     │   │ limit, SSE fan-out)  │
                    │ districts, alerts,   │   └──────────────────────┘
                    │ queries, evidence    │
                    └──────────────────────┘
```

### Key decisions (why)

- **API-first, pipeline-per-request.** Every chat request flows through the numbered stages. This makes each stage independently testable, debuggable, and swappable — the property the proposal demanded.
- **SSE over WebSocket for MVP.** Token streaming is enough for chat; WebSocket is reserved for future live alert push. MQTT: out.
- **Provider interface everywhere.** `WeatherProvider`, `LLMProvider`, `GeocoderProvider`, `SpeechProvider`, `MapProvider` — each with an adapter per vendor and a deterministic fallback.
- **PostGIS now, cheaply.** One Docker service; gives the geospatial story (district polygons, radius queries) without architecture weight.
- **Flutter web PWA first.** The demo runs on any judge's laptop/phone via a link; Android/iOS reuse the same codebase later. Voice input uses the browser Web Speech API through a JS interop bridge (Hindi is supported by Web Speech in Chrome).

---

## 4. Component Map

| Component | Responsibility | Files (planned) |
|-----------|---------------|-----------------|
| API layer | Routers, request validation, SSE streaming, rate limiting | `backend/app/api/*` |
| Query understanding | Intent + entity extraction → `QuerySpec` (typed JSON) | `backend/app/services/query_understanding/` |
| Orchestrator | Retrieval plan, parallel fetch, disambiguation | `backend/app/services/orchestrator.py` |
| Weather providers | IMD / Open-Meteo adapters → normalized `WeatherPayload` | `backend/app/providers/weather/` |
| Alert providers | SACHET CAP feed (live-verified: RSS index, CAP detail, location alerts, ETag caching); IMD district warnings land in Phase 4 | `backend/app/providers/alerts/` |
| Geocoder | Alias index + nearest-station + nearest-city (offline), Open-Meteo forward geocoding, BigDataCloud reverse, ambiguity flag (Phase 3) | `backend/app/services/location/` |
| Validation & fusion | Schema, plausibility, freshness, source ranking, provenance envelope — **gate implemented in Phase 2** (hard errors discard source, staleness surfaced) | `backend/app/services/validation/` |
| Risk layer | Warning-code → hazard/impact/action lookup (static, reviewed) | `backend/app/services/risk/` |
| Advisory KB | Curated do's/don'ts & explanations (JSON for MVP) | `backend/app/data/advisories/` |
| LLM provider | OpenAI-compatible (OpenAI/Groq) + Gemini adapters; fallback template responder | `backend/app/providers/llm/` |
| Response pipeline | Grounded generation, provenance check, official/AI labeling | `backend/app/services/response/` |
| DB layer | SQLAlchemy async models (cities, stations, source_registry, query_log), PostGIS geometry via idempotent `init_db` script | `backend/app/db/` |
| Cache | Redis TTL cache with fail-open semantics (obs 120s, forecasts 600s) between API and provider chain; rate-limit counters later | `backend/app/core/cache.py` |
| Observability | Structured JSON logs (structlog), request IDs, per-stage latency | `backend/app/core/logging.py` |
| Frontend | Flutter PWA: chat, cards, map, language, voice bridge | `frontend/` |

---

## 5. API Boundaries (public surface, v1)

All under `/api/v1`. JSON; `chat` streams via SSE.

| Endpoint | Purpose |
|----------|---------|
| `POST /chat` | Send a message → streamed grounded answer + structured cards (weather/alert/source) |
| `GET /weather?lat&lon` | Typed current-weather payload (for cards without chat) |
| `GET /forecast?lat&lon&from&to` | Typed forecast payload |
| `GET /alerts?district_id|lat&lon` | Official warnings affecting a location |
| `GET /locations/search?q` | City search with disambiguation candidates |
| `GET /locations/reverse?lat&lon` | Reverse geocode |
| `GET /sources` | Transparency registry: what sources exist, status, last fetched |
| `GET /health` | Readiness incl. provider health |

**Internal boundary (never public):** orchestrator ↔ providers, and the evidence bundle passed to the LLM. The LLM never calls weather APIs directly — it only receives the validated evidence bundle.

---

## 6. Database Schema (v1)

PostgreSQL + PostGIS. Key tables:

| Table | Purpose |
|-------|---------|
| `stations` | IMD stations: station_code, name, state, geom(point), source_id |
| `cities` | Curated cities: name, aliases (Hinglish/regional), district, state, geom(point) |
| `districts` | IMD district IDs + names + geometry (for warnings & map) |
| `alerts_cache` | Latest official warning per district: raw, normalized, color/code, issued/valid-until, fetched_at |
| `forecast_cache` / `obs_cache` | Normalized payloads keyed by location+horizon, with TTL + fetched_at |
| `queries` | Request log: query_text, QuerySpec, latency per stage, provider used, fallback flag |
| `evidence` | The evidence bundle per query (JSONB) — the audit trail for provenance |
| `responses` | Final text + cards + provenance check result |
| `source_registry` | Known sources, status (verified/authorized/planned), last_ok, notes |
| `advisory_items` | Curated do's/don'ts keyed by hazard + severity |

Redis holds hot cache (city forecasts ~10 min TTL, current obs ~5 min, alerts ~15 min) and rate-limit counters. Staleness is surfaced, never hidden.

---

## 7. AI Orchestration & Grounding Design

1. **QuerySpec** (structured output): `{intent, location:{name|lat,lon,confidence}, time:{anchor,window}, language, parameters[], wants_alerts, wants_advisory}`. Rule-based extractor first; LLM assist only for messy/Hinglish inputs.
2. **Retrieval plan**: orchestrator maps QuerySpec → provider calls. E.g., `current_weather` → IMD `current_wx` (station nearest) + fallback Open-Meteo; `rain_tomorrow_evening` → IMD 7-day city forecast (Day_2) or Open-Meteo hourly; alert intent → IMD `districtwarning` for the district.
3. **Evidence bundle** (the only thing the LLM sees): validated, normalized, schema-typed records, each with `{source_id, fetched_at, valid_from, unit, value, confidence}`. If a provider failed, the bundle explicitly contains a `data_gap` marker with the reason.
4. **Grounded generation**: system prompt fixes the LLM to evidence-only claims; tool calling is used only to pick from provided data, not to fetch; output is constrained (structured JSON → rendered as markdown + cards) so numbers stay typed.
5. **Provenance post-check**: extract every number from the final text; each must match a value in the evidence bundle (within unit rounding). Any number without provenance → response regenerated or the number removed. This is the hallucination firewall and a great demo.
6. **Safety rules** (always): never invent data; never upgrade/downgrade an official warning; official warnings rendered in an OFFICIAL WARNING block with source + issued/valid times; AI interpretation labelled as such; uncertainty phrased ("IMD expects…", "forecast confidence is moderate"); "I don't have data for that" instead of guessing.
7. **Fallback mode**: if the LLM provider fails, a template responder builds a grammatical answer from the evidence bundle directly. Identical provenance guarantees; only fluency differs.

---

## 8. Security Model (prototype-appropriate)

- **No user accounts for MVP** (public demo). Server-side secrets only; nothing LLM/API-key related ever shipped to the frontend.
- **Prompt-injection defence**: evidence-only context, tool-call allowlist, input length caps, system-boundary instructions; adversarial query set in tests.
- **Network**: providers are allowlisted hosts (no open SSRF); outbound timeouts; HTTPS behind a reverse proxy in deployment.
- **Rate limiting** per IP via Redis; CORS allowlist; request IDs for traceability.
- **Secrets**: `.env` (git-ignored) with `ENV`-driven config; Docker Compose for local/prod parity.

---

## 9. Development Order

> Phase numbers here are internal build-order labels (P1–P9). The project brief numbers
> phases as: P1 Architecture, P2 Data integration, P3 Backend, **P4 Frontend (active)**, P5
> Intelligence, P6 Testing, P7 Deployment, P8 SIH demo. Frontend work maps to the P6/P7
> rows below; Intelligence maps to P4/P5.

| Phase | Deliverable |
|-------|-------------|
| **P1 Architecture** | Step 1: this baseline (✅). Step 2: ADR + repo scaffold (backend/FastAPI, frontend skeleton, docker-compose, .env.example) |
| **P2 Data layer** | IMD + Open-Meteo + SACHET providers; validation/normalization; fixture-based tests; whitelisting application submitted |
| **P3 API core** | Location service (geocoding, aliases, disambiguation), DB schema + migrations, Redis cache, /weather /forecast /alerts endpoints |
| **P4 Intelligence** | QuerySpec extraction, orchestrator, tool layer, risk lookup, advisory KB |
| **P5 LLM response** | Provider adapters, evidence-bundle prompting, provenance check, fallback mode |
| **P6 Chat + frontend** | POST /chat (SSE), Flutter chat UI, weather/alert cards, source drawer |
| **P7 UX breadth** | Map, language selector (EN/HI +1), voice bridge (Web Speech) |
| **P8 Hardening** | Test matrix (hallucination, failures, stale data, wrong locations, multilingual, latency), demo script, failure drills |
| **P9 Deploy + demo** | Docker Compose, deployment, SIH demo run-through, Q&A prep |

---

## 10. Demo Scenarios (SIH)

1. "What's the weather in Kolkata right now?" → weather card + source card (IMD station, fetched time).
2. "Kal shaam Mumbai mein baarish hogi kya?" → Hindi/Hinglish → forecast grounded in Day-2 payload.
3. "There's a heavy rain warning in my area. What should I do?" → OFFICIAL WARNING block (IMD, orange/red, district) + plain-language explanation + do's/don'ts.
4. Location search + map pin + alert markers → spatial story.
5. Voice query (Hindi) → STT → answer → TTS.
6. **Failure drill**: kill the LLM key → deterministic fallback answers correctly with same provenance. (Judges love this.)
7. Source transparency tour: same question, /sources registry, timestamps.

---

## 11. Differentiators (feasible + impressive)

1. **Real IMD data + official warnings** (IP-whitelist application via the SIH channel) — "LLM explains, IMD evidences."
2. **Number-provenance firewall** — every number in every answer is traced to fetched evidence; hallucination structurally impossible to pass.
3. **Deterministic fallback** — the demo cannot die on a key outage.
4. **Official-warning integrity** — OFFICIAL WARNING vs AI interpretation is a hard UI + pipeline boundary.
5. **Multilingual + voice with zero paid dependencies** — Hindi/Hinglish chat and browser voice in the prototype, cloud providers behind interfaces for scale.