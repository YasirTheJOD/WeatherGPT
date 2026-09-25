# Architecture Decision Records

Short decision records for the SIH prototype. Status: **Accepted** unless noted. Each ADR records the decision and its consequences; revisit when a decision stops serving the demo.

---

## ADR-001 — Monorepo with `backend/`, `frontend/`, `infra/`, `docs/`

**Context:** Small team, hackathon timeline, one product.
**Decision:** Single repository, no microservices.
**Consequences:** One CI surface; services stay independently deployable via Docker; K8s migration later is config, not code (services are stateless).

## ADR-002 — Backend: Python + FastAPI, API-first

**Context:** Proposal's chosen stack; needs async, typed payloads, streaming.
**Decision:** FastAPI + Pydantic v2 + httpx. All external access goes through FastAPI; no client talks to providers directly.
**Consequences:** Typed schemas double as docs (`/docs`); SSE added in Phase 6 for chat streaming; WebSocket deferred.

## ADR-003 — Provider interfaces for everything external

**Context:** LLM provider, weather provider, speech, map must be swappable without rewrites.
**Decision:** `WeatherProvider` (IMD + Open-Meteo adapters) and `LLMProvider` (Phase 5) protocols; a `ProviderRegistry` encodes preference order (IMD primary, Open-Meteo fallback). Raw vendor payloads never leave the provider layer — they are normalized into domain models carrying a `Provenance` envelope.
**Consequences:** New sources = new adapter + config, not new plumbing. Provenance is structural, which makes source transparency free.

## ADR-004 — IMD primary, Open-Meteo fallback

**Context:** IMD is authoritative but requires an API key + IP whitelisting; the demo must work before that is granted.
**Decision:** Both providers implement the same interface; registry order = IMD then Open-Meteo. IMD fails closed (no silent degradation), Open-Meteo carries the demo until the key arrives.
**Consequences:** A config change (adding the key) upgrades data authority — no code change.

## ADR-005 — LLM grounding: evidence-bundle-only, number-provenance post-check, deterministic fallback

**Context:** Disaster-safety product; hallucination is unacceptable; demos must survive key outages.
**Decision:** The LLM sees only the validated evidence bundle; never calls weather APIs; every number in the final answer must match the evidence (provenance check); a template responder produces grounded answers when no LLM key is configured.
**Consequences:** Slightly less "magic" in answers; vastly safer; the demo cannot die on a key outage.

## ADR-006 — Risk levels only from a static, human-reviewed lookup table

**Context:** "Risk & impact analysis" must not invent severity.
**Decision:** IMD warning codes/colors map to hazard category and plain-language guidance through a curated table. The LLM is banned from assigning severity.
**Consequences:** Official warnings stay authoritative; AI interpretation is clearly separate.

## ADR-007 — Frontend: Flutter web PWA first (single codebase)

**Context:** Mobile-first product; SIH demos happen on arbitrary laptops/phones.
**Decision:** Flutter with `web,android,ios` platforms; demo runs from a URL; voice via browser Web Speech API through a JS bridge (zero API keys); cloud STT/TTS behind an interface later.
**Consequences:** One codebase covers PWA + future native apps; voice quality is browser-dependent in the prototype.

## ADR-008 — PostGIS + Redis via Docker Compose (no K8s, no MQTT)

**Context:** Proposal wants K8s-ready but the brief also says don't over-engineer.
**Decision:** Compose runs `backend + postgis + redis`. PostGIS gives the geospatial story cheaply; Redis caches + rate-limits. SSE for chat; WebSocket/MQTT deferred to post-demo.
**Consequences:** Full stack runs on one machine; scale story is documented, not built.

## ADR-009 — Advisory KB as curated JSON, no vector DB in MVP

**Context:** "RAG" in the proposal implies document retrieval.
**Decision:** Weather data comes from APIs, not documents; RAG scope = a small human-reviewed advisory KB (do's/don'ts, explanations). Vector search is a planned post-MVP enhancement.
**Consequences:** Simpler, auditable, no embedding infra; demo still shows grounded "what should I do" answers.

## ADR-010 — No user accounts for the MVP

**Context:** Public demo; security must be real but proportionate.
**Decision:** No auth in the prototype; server-side secrets only; rate limiting via Redis; provider hosts allowlisted (no open SSRF); prompt-injection defenses in the LLM pipeline.
**Consequences:** Shorter path to demo; auth design is documented in the architecture baseline for later.

---

## ADR-011 — SACHET alerts: official CAP feed with ETag caching; pass-through integrity

**Context:** NDMA's portal is the official warning channel; its `/CapFeed` page is a SPA hiding real endpoints.
**Decision:** Use the live-verified endpoints (RSS index `cap_public_website/rss/rss_india.xml`, per-alert CAP via `FetchXMLFile?identifier=`, location query `FetchLocationWiseAlerts`) with the **mandatory ETag caching** from NDMA's own integration guide. Alerts are passed through as-is with provenance — no transformation of severity/urgency/certainty, no LLM in the alert path. Unknown feed identifiers return 200-with-HTML-404, so parsing failures are treated as provider errors.
**Consequences:** Official warnings stay authoritative; polls are cheap (304 short-circuits); the discovery process and evidence are recorded in `docs/DATA-SOURCES.md`.

## ADR-012 — Validation gate in the provider chain

**Context:** Corrupt or stale payloads must not reach users or the LLM.
**Decision:** A `ValidationService` (plausibility bounds + freshness) sits in the provider registry: hard errors (impossible values, inverted min/max) discard the provider result and try the next source; staleness is a surfaced warning, never silent. Every response carries a validation report next to its provenance.
**Consequences:** The demo degrades gracefully on bad data and can show the validation layer working; bounds are deliberately wide so the system never second-guesses real meteorology.

---

## ADR-013 — Redis cache with fail-open semantics, between API and provider chain

**Context:** Frequent queries, provider rate limits, and demos that must survive Redis being absent.
**Decision:** A `CacheService` (Redis, JSON) wraps the provider chain in the registry: `weather:current` TTL 120s, `weather:forecast` TTL 600s. Redis failures are **fail-open** — `get` returns a miss, `set` is a no-op — so a missing Redis degrades to live fetches, never errors. Corrupt cache entries are discarded and refetched.
**Consequences:** Fast repeat queries; the demo runs with zero infrastructure if needed; rate-limit counters slot into the same service later.

## ADR-014 — Location resolution: aliases first, geocoder second, ambiguity is explicit

**Context:** Duplicate Indian place names and Hinglish spellings make location the hardest part of a conversational weather system.
**Decision:** Resolution = curated alias index (offline, deterministic, highest confidence) → Open-Meteo forward geocoding (India-preferred; IN matches filtered, all matches kept when none are Indian) → dedupe by proximity → rank by confidence. When the top candidates are close in confidence the result is flagged `ambiguous` and the caller (chat orchestrator in Phase 4) asks the user to pick. Reverse = offline nearest curated city first, BigDataCloud second. Geocoder outages degrade to alias-only, never errors.
**Consequences:** Deterministic fast path for major cities, live coverage elsewhere, and a structured disambiguation loop instead of guessing — which is both safer and a good demo.

---

*Deviating from any ADR requires updating this file with the new decision and its consequences.*