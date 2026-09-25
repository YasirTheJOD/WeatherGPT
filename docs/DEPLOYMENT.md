# WeatherGPT — Deployment (Phase 7)

> Status: **Implemented** for the SIH prototype. One compose file brings up the API,
> PostGIS and Redis; an optional `web` profile serves the Flutter PWA through nginx and
> reverse-proxies the API on the same origin.

---

## 1. What runs

| Service | Image / build | Host port | Role |
|---------|---------------|-----------|------|
| `backend` | `backend/Dockerfile` → `weathergpt-backend:local` | **8000** | FastAPI: `/chat` (SSE), `/weather`, `/forecast`, `/alerts`, `/locations`, `/sources`, `/health` |
| `postgis` | `postgis/postgis:16-3.4` | — (internal) | Schema (cities, stations, source registry, query log) + PostGIS geometry |
| `redis` | `redis:7-alpine` | — (internal) | TTL cache + rate-limit counters (no persistence: it's a cache) |
| `web` *(profile)* | `nginx:1.27-alpine` | **8080** | Serves the built Flutter web PWA; proxies `/api/` → `backend:8000` |

Postgres and Redis are **not** published to the host. Neither the API nor the app can
silently degrade into "no cache, no rate limit" by accident; both still *fail open* by
design when those layers are down (see §6).

---

## 2. Prerequisites

- Docker Engine + Compose v2 (`docker compose version`).
- A root `.env` (step 3). IMD credentials are optional — without them the stack runs on
  the Open-Meteo fallback exactly as the architecture intends.
- Flutter SDK **only** if you want the `web` profile (it needs a built bundle).

---

## 3. Configure

```bash
cp .env.example .env      # from the repository root
```

`.env` is git-ignored and is injected into the `backend` container by
`infra/docker-compose.yml` via `env_file: ../.env`. Two values are overridden **inside**
the compose network, because `localhost` inside a container is the container itself:

```
REDIS_URL    = redis://redis:6379/0
DATABASE_URL = postgresql+asyncpg://weathergpt:weathergpt@postgis:5432/weathergpt
```

Everything else in `.env` is the same knob you use locally — see `.env.example` for the
full list. The ones that matter in deployment:

| Variable | Default | Notes |
|----------|---------|-------|
| `APP_ENV` | `development` | Set to `production` for a deployed demo |
| `LOG_LEVEL` | `INFO` | Logs are structured JSON (§6) |
| `CORS_ORIGINS` | `…localhost:5173,…localhost:8080` | Only relevant when the PWA calls the API cross-origin |
| `IMD_API_KEY` | *(empty)* | When granted, IMD becomes primary automatically |
| `LLM_PROVIDER` | `fallback` | `groq` / `openai` / `gemini` + the matching key; a runtime failure falls back |
| `RATE_LIMIT_*` | `60 / 60s` | Redis fixed window per client IP; health is exempt |

> **Why no `${VAR}` interpolation in the compose file:** Compose interpolates from the
> *compose file's* directory, so a root `.env` would be ignored by `-f infra/…`.
> `env_file` injects the root file at runtime regardless of where you invoke compose.

---

## 4. Run

### API + PostGIS + Redis

```bash
docker compose -f infra/docker-compose.yml up --build -d
```

The container runs `python -m app.scripts.init_db` before uvicorn, so schema, PostGIS
geometry, city seeds, the source registry and the station snapshot are applied on every
boot (the script is idempotent).

Verify:

```bash
curl -s http://localhost:8000/api/v1/health | jq
curl -s http://localhost:8000/api/v1/sources | jq '.counts'
open http://localhost:8000/docs
```

### Full demo (adds the web front end)

```bash
cd frontend
flutter build web --release --dart-define=API_BASE_URL=http://localhost:8080
cd ..
docker compose -f infra/docker-compose.yml --profile web up --build -d
open http://localhost:8080
```

Build the PWA against the **nginx origin** (`:8080`), not the API port: nginx proxies
`/api/` on the same origin, so the browser makes no cross-origin request and there is no
API host baked into the client bundle. For a LAN demo, replace `localhost` with the host's
address (and add it to `CORS_ORIGINS` only if you bypass the proxy).

### 4b. One URL, no second host (LAN, tunnel, or a single free service)

The API can serve the built PWA itself, so the whole app is **one origin on one port** —
the shape you want when you only get one public URL (a tunnel, or a free host that gives
you a single service):

```bash
cd frontend && flutter build web --release --dart-define=API_BASE_URL= && cd ..
cd backend && WEB_DIR=../frontend/build/web python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- `http://<host>:8000/` → the PWA (client-side routes fall back to the shell)
- `http://<host>:8000/api/v1/...` → the API · `/docs` → API docs

An **empty** `--dart-define=API_BASE_URL=` means *call whatever origin served the page*.
That is deliberate: nothing is baked into the bundle, so the same build works behind a
tunnel, a LAN IP or a real domain, and CORS never enters the picture. Omit the define
entirely and you get the `localhost:8000` dev default instead — a build that looks fine and
answers only on the machine that made it.

`WEB_DIR` is relative to the directory you start the server in, and it is **off by
default** (API only), so nothing changes for the normal `flutter run` flow. A typo'd path
logs `web_dir_missing` and degrades to API-only rather than pretending to work.

> `flutter build web` is the only thing that compiles the **web** branch of the app's
> conditional imports; `flutter test` runs on the VM and never sees it. A missing web
> factory has already shipped a green test suite on top of a build that would not compile,
> so always build the bundle — not just run the tests — before a deployment.

---

## 5. Operational commands

```bash
# Follow logs (JSON lines; request IDs make a single request greppable)
docker compose -f infra/docker-compose.yml logs -f backend

# Open a psql shell (Postgres is not published to the host)
docker compose -f infra/docker-compose.yml exec postgis psql -U weathergpt -d weathergpt

# Inspect the rate-limit counters / cache keys
docker compose -f infra/docker-compose.yml exec redis redis-cli keys 'wgt:*'

# Restart just the API after an env change
docker compose -f infra/docker-compose.yml up -d --force-recreate backend

# Stop, and optionally wipe the database volume
docker compose -f infra/docker-compose.yml down
docker compose -f infra/docker-compose.yml down -v        # destroys pgdata
```

---

## 6. Production notes

- **TLS / reverse proxy.** Terminate HTTPS in front of the stack (Caddy, nginx with
  certbot, or a cloud load balancer) and forward to `:8080` (web) or `:8000` (API).
  Trim `CORS_ORIGINS` to the real origin. The API sets `X-Accel-Buffering: no` on
  `/chat`, and `infra/nginx.conf` disables `proxy_buffering` — keep that for any proxy
  you add, or the SSE token stream stalls.
- **Rate limiting behind a proxy.** `RateLimitMiddleware` keys on the first
  `X-Forwarded-For` hop (falling back to the socket peer). Make sure your proxy *sets*
  that header and that it is not client-spoofable at the edge.
- **Worker count.** One uvicorn process is enough for the demo. Scaling to
  `--workers N` is safe for the API, with one caveat: the SACHET ETag is held in
  `app.state` per process, so each worker revalidates the CAP feed independently
  (correct, just less shared). Redis already carries the cache and rate-limit state.
- **Secrets.** `.env` never enters the image (`backend/.dockerignore`) and is git-ignored.
  LLM/API keys are server-side only; nothing key-related is shipped to the browser.
- **Backups.** The database is optional to the app's operation (it fails open), but if you
  care about the audit trail, back up the `pgdata` volume.
- **Observability.** Every response carries `X-Request-ID` (incoming values are echoed)
  and every log line is JSON stamped with it — grep one ID to reconstruct a request.

---

## 7. Failure behaviour (the demo does not die)

| Failure | Behaviour |
|---------|-----------|
| LLM key missing / provider down / provider bug / blank answer | Deterministic responder answers from the same evidence bundle (SSE `meta.fallback = true`) |
| A weather provider returns corrupt data | Hard validation discards it and the next provider is tried |
| Data is stale | Served, with a `stale` warning and the fetch time in provenance — never hidden |
| Redis down | Cache and rate limiting fail open; requests are served, nothing is rejected |
| Postgres down | App starts and answers; DB-backed logging is skipped |
| IMD not yet authorized | Open-Meteo serves weather; `/sources` reports IMD as unavailable |

---

## 8. Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `env file …/.env not found` | Run `cp .env.example .env` at the repository root |
| `port is already allocated` | Something else owns 8000/8080 (e.g. a local uvicorn) — stop it or change the mapping |
| Backend restarts in a loop | `docker compose … logs backend`; usually the DB wasn't ready — the `service_healthy` gate should prevent this, so check the `postgis` healthcheck |
| `web` profile serves 404 at `/` | `frontend/build/web` is missing — run `flutter build web` (see §4) |
| Chat answer appears all at once / stalls | A proxy is buffering the SSE stream — set `proxy_buffering off` (see §6) |
| `/sources` shows IMD unavailable | Expected until the key/whitelist is granted — see `docs/IMD-ACCESS.md` |

---

## 9. A permanent public URL (Render free plan, no credit card)

Because the app is **one origin** (§4b), publishing it needs exactly one host and no CORS
work. Render's free plan runs it at no cost and **without a credit card**, which is why it is
the recommended host here. (Koyeb by contrast requires a card on file — their FAQ confirms a
$29 pre-authorization — so it is not a no-card option.)

### 9.1 What is already in the repository

| Path | Role |
|------|------|
| `render.yaml` | Blueprint: one free web service, `healthCheckPath: /api/v1/health`, `WEB_DIR=../frontend/build/web` |
| `frontend/build/web` | The **built PWA, committed** (~4.6 MB). Render builds from Git and never runs Flutter, so `buildCommand` is only `pip install ./backend` |
| `scripts/build_web.sh` | Rebuilds that bundle: release + same-origin + CDN CanvasKit, then strips the unused 37 MB local copy |
| `.github/workflows/keepalive.yml` | Pings `/api/v1/health` every 10 min so the free instance stays awake |

### 9.2 Deploy (one time)

```bash
# 1. The Blueprint deploys from a Git repository:
git remote add origin https://github.com/<you>/weathergpt.git
git push -u origin main

# 2. Render Dashboard -> New + -> Blueprint -> pick this repo -> Apply.
#    It reads render.yaml and creates the service. No card, no other settings.
```

The service URL is `https://<service-name>.onrender.com`. If the name is already taken,
Render appends a suffix — open the service page, copy the real URL, and update
`.github/workflows/keepalive.yml` to match.

### 9.3 Verify the deployment

```bash
curl -s https://<service>.onrender.com/api/v1/health | jq '.status, .providers'
curl -s https://<service>.onrender.com/api/v1/sources | jq '.counts'
cd backend && python -m app.scripts.demo_smoke --base-url https://<service>.onrender.com
```

Then open the URL: the PWA loads, calls the API on its own origin, and — on a phone —
**Add to Home Screen** gives it a standalone icon and window. That is the "app" the demo
needs; no APK, store or JDK is involved.

### 9.4 What the free plan costs you (the honest list)

- **Sleeps after 15 minutes idle**, and the next request waits ~40–60 s for it to boot. The
  keep-alive workflow is what hides that; delete it if you would rather not run Actions.
- **Make the GitHub repository public.** Actions minutes are free and unlimited on public
  repos, but on a **private** repo each keep-alive run rounds up to one billed minute, so an
  every-10-minute cron is ~4,300 minutes/month against GitHub's 2,000 free minutes. Nothing
  secret lives in the repo (keys go in Render's dashboard via `sync: false`), so public is
  the sane default here.
- **0.1 CPU / 512 MB and ~5 GB bandwidth per month** — plenty for this, not a scale plan.
- **No Redis and no Postgres**: cache and rate limiting fail open, and `RATE_LIMIT_ENABLED`
  is `false` in the Blueprint because without Redis every request would pay a ~2 s failed
  connect before failing open anyway (it never rejects anything in either case).
- **No IMD key**: Open-Meteo serves the weather and `/api/v1/sources` keeps saying
  `Requires authorization` — which is the honest state, so leave it visible.
- **CanvasKit (the UI renderer) comes from Google's gstatic CDN**, because the release recipe
  uses `--web-resources-cdn` to keep the committed bundle at 4.6 MB instead of 41 MB.

### 9.5 Redeploying a frontend change

```bash
bash scripts/build_web.sh                 # rebuild the committed bundle
```
then commit `frontend/build/web` and push; `autoDeploy: true` redeploys on push. The PWA's
service worker may serve a cached shell after a redeploy — a hard refresh (or a new
deployment) clears it.

### 9.6 Status — what this path has actually been proven to do

**Deployed and verified 2026-09-25** at https://weathergpt-7vnu.onrender.com, from
`github.com/YasirTheJOD/WeatherGPT`, with `render.yaml` applied as a Blueprint exactly as
§9.2 describes — including `region: singapore`, which Render accepted.

Verified against the public origin, not locally: `/` returns the PWA shell (and a deep link
falls back to it), `/api/v1/health`, `/api/v1/sources`, `/docs` and `/main.dart.js` all
respond, and the browser calls the API on its own origin — so the `WEB_DIR` one-origin design
works in production. SACHET alerts, geocoding, Devanagari resolution and the safety scenario
all pass over HTTPS.

**The first `demo_smoke` run scored 5/8, and the three failures were one upstream problem.**
Open-Meteo's free tier allows **one concurrent request per IP**, and shared hosting egress
cannot reliably hold it: `api.open-meteo.com` returned `429` on 0/18 requests over ~110s,
while `geocoding-api.open-meteo.com` on the same deploy answered `200`. The app degraded
correctly — the chain fell back to an honest "no live data" gap and alerts and the registry
kept working — but with a single fallback the weather is simply absent, which is why the
weather chain now carries a second keyless fallback, MET Norway. Full measurement and
interface notes: `DATA-SOURCES.md` §6. **Re-run the rehearsal after any provider-chain
change**, and expect the first request to be slow if the free instance has slept (15 min
idle).

Still unproven: the **container** path. No image was built for the Render deploy (Render
builds Python natively), so §1–§8 stay *reviewed, not proven* until a real
`docker compose -f infra/docker-compose.yml up --build` on a Docker machine passes
`demo_smoke` against the container.

The contract those sections rest on is now pinned statically by
`backend/tests/test_container_assumptions.py` (27 tests: packaging, dependency closure,
Linux-vs-Windows path traps, `.dockerignore` vs runtime needs, Dockerfile and compose
coherence). That narrows the remaining risk to the image build and `init_db` — but it is not a
substitute for the real `up`.
