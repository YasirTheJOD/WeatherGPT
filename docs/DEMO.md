# WeatherGPT — Phase 8 SIH Demo Script

> The 8-minute jury walkthrough. Scenario list: [`ARCHITECTURE.md`](ARCHITECTURE.md) §10.
> Stack + ports: [`DEPLOYMENT.md`](DEPLOYMENT.md). Evidence for every data claim:
> [`DATA-SOURCES.md`](DATA-SOURCES.md).
>
> **Rehearse with one command** (see §4): `python -m app.scripts.demo_smoke --base-url http://localhost:8000`

---

## 0. The framing (say this first, and again at the end)

> "**Meteorological systems provide the evidence; the AI explains it.** We never let the
> model invent a number, and we never relabel an official warning. And if the model or a data
> API dies mid-demo, the system still answers with the same provenance — let me show you."

Every claim in this script is labelled the way the project labels things: `Implemented` ·
`Prototype` · `Requires authorization` · `Future scope`.

---

## 1. Pre-flight (T-15 minutes)

```bash
cp .env.example .env          # IMD_API_KEY optional; everything else has defaults

# A) Local API, then the rehearsal (the smoke run is the checklist gate)
cd backend && .venv/Scripts/python -m uvicorn app.main:app --port 8000 &
.venv/Scripts/python -m app.scripts.demo_smoke --base-url http://localhost:8000
```

Or the full Docker stack — note the Flutter bundle must exist **before** the `web` profile
starts, because nginx mounts `frontend/build/web` read-only:

```bash
cd frontend && flutter build web --release --dart-define=API_BASE_URL=http://localhost:8080 && cd ..
docker compose -f infra/docker-compose.yml --profile web up --build -d
cd backend && .venv/Scripts/python -m app.scripts.demo_smoke --base-url http://localhost:8000
```

| Check | Expect | If it differs |
|---|---|---|
| `demo_smoke` result | **8/8 scripted scenarios passed**, exit 0 | Read the FAIL lines — each names the broken piece |
| `flutter build web --release` | **`√ Built build\web`** | It is the only step that compiles the web branch of the app — `flutter test` runs on the VM and stays green while the release build is broken. Fix the compile error before the demo |
| `http://localhost:8080` loads the PWA | chat tab with the 4 starter prompts | Missing? `flutter build web` didn't run — see [`DEPLOYMENT.md`](DEPLOYMENT.md) §8 |
| `/api/v1/sources` → IMD | **`available: false`, "Requires authorization"** | This is *expected, not a bug* — say it before a judge finds it |
| `/api/v1/sources` → SACHET | **available** — official NDMA feed, labelled `Prototype` (verified live) | If down, the alerts scenario degrades to "no warnings" |
| Browser mic permission | granted (for scenario 5) | Otherwise type the Hindi question |
| LLM provider | `fallback` (no keys needed) **or** a working key | A broken key still works — that's scenario 6 |
| Redis / Postgres | up (stack) | Both **fail open**; nothing to do |

Open a second browser tab on `/api/v1/sources` and a third on `/docs` — scenario 7 uses them.

---

## 2. Run sheet (8 minutes)

### 0:00 — Frame it (§0 above), then start with the friendly question.

### 0:40 — Scenario 1 · "What's the weather in Kolkata right now?"
Type **exactly**: `What's the weather in Kolkata right now?`

The answer **streams in word by word** (SSE `delta` frames; the caret shows it is still
being written). Then, on completion: a conditions card (temperature, condition, humidity,
wind, pressure, rain), the **source card** (Open-Meteo, fetched-at timestamp), and follow-up
chips. The cards arrive with the finished answer, never before it — the text can stream, the
structured evidence cannot be guessed at.

Live example from the rehearsal run:
```
Right now in Kolkata: 26°C, Moderate drizzle — humidity 94%, wind 16 km/h ESE, pressure 1005 hPa, rain 0.2 mm.
```
> **Read the examples below as shape, not script.** They are real output from the
> 2026-09-24 rehearsal, so temperatures, warning counts and calendar dates will differ on
> demo day. What must not differ: the cards, the source card with its fetched-at timestamp,
> the right city, and `provenance_check.verified = true`.

Say: *"Every number on screen came from the provider, not from the model — and the card says
which provider and when it was fetched."*

### 1:50 — Scenario 2 · the Hinglish question
Type: `Kal shaam Mumbai mein baarish hogi kya?`

What appears: a 7-day forecast card with **day 2** highlighted, phrased for tomorrow evening.

Live example:
```
Tomorrow evening (Fri 25 Sep) in Mumbai: high 30°, low 24°, rain 3.9 mm, Light rain showers.
```
Say: *"'Kal shaam' means tomorrow evening — it parsed the language, the day offset and the
place, and answered from the forecast payload."* (Rubric point: multilingual + grounded.)

### 3:00 — Scenario 3 · official warnings
Type: `Is there a heavy rain warning in my area? What should I do?` (allow location first)

What appears: **OFFICIAL WARNING** block(s) — event, severity, issued/expires, affected areas,
do's/don'ts — with the SACHET/NDMA source card.

Live example from the rehearsal run (one live warning near Kolkata that day — the count
follows the official feed, so it can be zero):
```
1 official warning(s): There is an official warning for Kolkata: Light Thunderstorm with
surface wind (Moderate).
```
Say: *"These are CAP alerts published by NDMA — an official feed, labelled `Prototype` in our
source list because the integration is young, not because the data is unofficial. They are
passed through untouched: the app never upgrades or downgrades a severity. The AI text
explains them; the warning block is the official record."*

### 4:15 — Scenario 4 · location search + map
Weather tab → type `Kolkata` in the search bar → pick the candidate → Map tab.

What appears: a pin on the selected place and the **actual CAP alert footprints** (circles /
polygons from the alert areas) drawn in severity colours, plus the map's source strip
(OpenStreetMap, SACHET).

Say: *"Search, disambiguation, the map pin, and the alert geometry all come from the same
resolved location — one place across every tab."*

### 5:15 — Scenario 5 · voice, in Hindi
Tap the mic and ask in Hindi: **"कल दिल्ली में बारिश होगी क्या?"**

(If the mic misbehaves, type it — Devanagari text resolves the same way.)

What appears: the transcript as a user bubble, the grounded answer, then the answer **spoken
back** (browser TTS, Hindi voice).

Live example from the rehearsal run:
```
दिल्ली → Delhi: Tomorrow (Fri 25 Sep) in Delhi: high 34°, low 24°, rain 0 mm, Mainly clear.
```
Say: *"Zero paid speech APIs — browser STT/TTS, with the cloud providers behind an interface
for later. And note it resolved दिल्ली: Devanagari city names come from our curated offline
alias index, because the geocoder only takes Latin script — that's the difference between a
Hindi demo and a Google-Translate demo."*

### 6:00 — Scenario 6 · **the failure drill** (do this one even if time is short)
Ask for the weather again, then break the LLM live (see §3) and ask once more.

What appears: the **same structured answer with identical provenance**, only less fluent. The
SSE `meta` frame flips `fallback: true`.

Say: *"The model is gone. The answer is not. Same numbers, same source card, same warnings —
because the deterministic responder builds the sentence from the evidence bundle."*

### 7:00 — Scenario 7 · transparency + the hallucination firewall
Open the **sources drawer**, then the `/api/v1/sources` tab, then `/docs`.

What to point at:
1. The live registry: **9 sources, 6 available, 3 official** — and IMD honestly marked
   `Requires authorization`.
2. Every answer carries source + fetched-at; the drawer's per-source status tracks the live
   config (it flipped to **5/9** when we broke the LLM key).
3. Ask an unanswerable question — `What's the weather in xyzzy-not-a-place?` — and show it
   **refusing** instead of inventing: *"I couldn't find a place called …"*.

Live example:
```
I couldn't find a place called "xyzzy not a place". Try a different spelling or pick a starter question below.
```
Say: *"This is the hallucination firewall: evidence-only grounding, a number-provenance
post-check on every answer, and a hard refusal when there is nothing to ground on."*

---

## 3. Failure drills — how to trigger, what you'll see, what to say

| Drill | Trigger | What you'll see | Say |
|---|---|---|---|
| **LLM provider outage** | `LLM_PROVIDER=groq GROQ_API_KEY= uvicorn app.main:app --port 8011` (or just break the key) | Identical answer, `meta.fallback: true`; `/sources` reports the LLM as unavailable | "The demo cannot die on a key outage." |
| **Weather provider outage** | `OPEN_METEO_BASE_URL=http://127.0.0.1:9 uvicorn app.main:app --port 8012` | *"I don't have live data for that right now."* — **never** a stack trace; alerts + registry still work | "We'd rather say 'I don't know' than invent a temperature." |
| **Redis down** | `docker compose -f infra/docker-compose.yml stop redis` | Chat keeps answering; rate limiting + cache fail open | "The cache is an optimisation, not a dependency." |
| **Postgres down** | `… stop postgis` | App answers; DB-backed query logging is skipped | "Same — it degrades, it doesn't break." |
| **Source registry unreachable** | Open the sources drawer with the API stopped | Built-in source list + explicit error banner + **Retry** | "Transparency never depends on the network." |
| **IMD granted** | Set `IMD_API_KEY=…` and restart | `/api/v1/sources` flips IMD to `Available`; IMD becomes primary automatically | "Authorization is a config change, not a rework." |

Rehearse the two scriptable drills with the flags in §4 — both are verified working.

---

## 4. Rehearsal routine

`backend/app/scripts/demo_smoke.py` drives every scenario that can be scripted and asserts
what the demo promises (provenance verified, right place, right day, graceful degradation).
It exits non-zero on failure, so it doubles as the pre-demo gate.

```bash
cd backend

# 1) Normal: live data, deterministic responder.
python -m app.scripts.demo_smoke --base-url http://localhost:8000

# 2) LLM outage drill (start a second API with a broken provider first)
LLM_PROVIDER=groq GROQ_API_KEY= uvicorn app.main:app --port 8011 &
python -m app.scripts.demo_smoke --base-url http://localhost:8011 --expect-llm-fallback

# 3) Provider outage drill (dead upstream)
OPEN_METEO_BASE_URL=http://127.0.0.1:9 uvicorn app.main:app --port 8012 &
python -m app.scripts.demo_smoke --base-url http://localhost:8012 --expect-provider-outage
```

Expected: **8/8 scripted scenarios passed**, exit 0, in all three modes (rehearsed 2026-09-19
and again 2026-09-24). Each run is well under a minute. Re-run all three the morning of the
demo; the live examples quoted in §2 are from those runs.

On Windows, redirecting this output (`| tee rehearsal.log`) used to kill the report with a
`UnicodeEncodeError` *after* every scenario had run — the run was green and the verdict was
lost. The harness now forces UTF-8 on `stdout`, so piping and logging the gate is safe.

Manual steps the harness cannot cover (it prints the same list): the map gestures, the voice
loop (its API half *is* scripted — `दिल्ली` must resolve), reading the warning block aloud, and
the drawer tour.

---

## 5. Q&A prep

| Likely question | Crisp answer |
|---|---|
| "Isn't this just ChatGPT with a weather API?" | The LLM **never** calls a weather API and never sees the network. It receives one validated evidence bundle and returns text only; cards, suggestions and the location come from the evidence. Numbers are post-checked against that bundle. |
| "Does Hindi actually work, or is it just translation?" | It's parsed, not translated. Intent, day offset and place are extracted from the Hindi/Hinglish text itself (`कल` → tomorrow, `शाम` → evening), and **Devanagari place names resolve through the curated offline alias index** — the geocoder can only be searched in Latin script, so that index is what makes `दिल्ली` work deterministically. Answers and the UI are localized, and voice is browser STT/TTS in Hindi with zero paid APIs. English, Hindi and Hinglish are covered today; another language is dictionary work against the same parser. |
| "How do you stop hallucination?" | Three structural layers: evidence-only prompting, a **number-provenance firewall** (every number must exist in the fetched evidence), and a hard refusal when a place can't be resolved. Plus the deterministic fallback, which passes by construction. |
| "Is the data official?" | Official warnings come from the NDMA **SACHET CAP feed** (live, verified — `Prototype` label means *new integration*, not unofficial data) and are passed through untouched. Weather is IMD-primary (we're honest: `Requires authorization` today) with Open-Meteo as a clearly-labelled GFS-derived fallback. |
| "When will IMD be live?" | The moment the key/whitelist lands — it's a config change; `/sources` flips to Available and the provider chain prefers IMD automatically. See [`IMD-ACCESS.md`](IMD-ACCESS.md). |
| "Why does the sources panel say Open-Meteo is available while the answer said 'no live data'?" | Because `available` on that endpoint means *configured and usable without authorization* — it is not a reachability probe. We chose that deliberately: the endpoint must be O(1) and never block or fail on a third party, so reachability is evidenced **per answer** by the source card and by the honest "I don't have live data" gap. One flag, one meaning; the two claims never contradict each other. |
| "What's your forecast accuracy?" | We don't claim any. We relay IMD/GFS values with attribution and timestamps, because accuracy is the forecast model's claim to make — not ours. |
| "Will it work on a weak connection?" | Small JSON payloads, SSE text streaming, per-datatype TTL caching, and a provider chain with a fallback. Nothing heavy is on the critical path. |
| "How does it scale?" | Stateless FastAPI behind a proxy, Redis for cache + rate limiting, PostGIS for geospatial. Compose today; Kubernetes is a config change, not a rewrite. |
| "Why not run WRF/GFS yourselves?" | Deliberately out of MVP scope: raw GRIB ingestion is a project of its own. Open-Meteo already serves GFS-derived point forecasts; raw model output is future map-layer scope. |
| "Privacy / security?" | No accounts, no personal data stored. Server-side keys only, CORS allowlist, request IDs on every response, per-IP rate limiting, prompt-injection defences, and an adversarial test matrix covering wrong locations, multilingual input, stale data and provider outages. |
| "What's next?" | Finish IMD authorization, the advisory knowledge base (do's/don'ts lookup), LLM-assisted query parsing behind the existing interface, and a live alert push channel. |

---

## 6. If something breaks mid-demo

| Symptom | Do this |
|---|---|
| LLM key stops working | **Keep going** — say "this is scenario 6" and let the fallback answer. |
| Weather provider unreachable | Keep going — the answer names the gap honestly; pivot to alerts/map. |
| Mic permission denied / no Hindi voice | Type `कल दिल्ली में बारिश होगी क्या?` and read the answer aloud. |
| Map tiles blank | Skip the map, show the alert cards + `/api/v1/sources` instead. |
| Backend/stack dies | Fall back to the recorded screencast and keep narrating; the drill table above still stands. |
| A judge asks a question you can't answer | Say "that's pending authorization / future scope" — the labels in this repo exist so you never have to bluff. |
