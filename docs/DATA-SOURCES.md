# WeatherGPT — Data Source Integration Matrix

> Status labels used across this project: **Implemented** · **Prototype** · **Planned** · **Requires authorization** · **Future scope**.
> Every row was verified on **2026-09-06** via the linked authoritative source. Nothing here is assumed.

---

## Summary Table

| Source | Status for SIH prototype | Auth required | Verified interface | Role in MVP | Evidence |
|--------|--------------------------|---------------|--------------------|-------------|----------|
| **IMD API Management Platform** (`api.imd.gov.in`) | **Requires authorization** — live probe (2026-09-06) returned `{"error":"API key missing"}`; apply early; strongest data | **API key** (auth mechanism TBD — header vs query param) + IP whitelisting per IMD docs | Official REST API reference, endpoints verified | **Primary** authoritative observations, forecasts, district warnings | [API reference](https://api.imd.gov.in/public/api_reference.html), [IMD APIs page](https://mausam.imd.gov.in/responsive/apis.php), [access checklist](IMD-ACCESS.md) |
| **Open-Meteo** | **Prototype** (works today, no key) | None (free, non-commercial) | Forecast / geocoding / historical APIs | **Fallback + resilience layer** (GFS-derived), geocoding; **not** an IMD substitute | [open-meteo.com](https://open-meteo.com/), [docs](https://open-meteo.com/en/docs) |
| **SACHET / NDMA CAP feed** (`sachet.ndma.gov.in`) | **Prototype (verified live 2026-09-06)** — public, no auth | None | RSS index `cap_public_website/rss/rss_india.xml` (ETag + Last-Modified); per-alert CAP 1.2 XML via `FetchXMLFile?identifier=<guid>`; location alerts via `FetchLocationWiseAlerts`; mandatory ETag-based caching (official guide) | Secondary official warning source (alerts + advisory context); ETag caching implemented | [SACHET portal](https://sachet.ndma.gov.in/), [Integration Guide PDF](https://sachet.ndma.gov.in/docs/Integration_Guide_For_Agencies.pdf) |
| **MOSDAC (ISRO/SAC)** | **Requires authorization; Future scope** | MOSDAC account (registration + approval), username/password | Bulk satellite-data download API (Python `mdapi.py` + `config.json`, 5,000 files/day cap) | Not needed for MVP core; future satellite imagery / cyclone layers | [Download API manual](https://mosdac.gov.in/downloadapi-manual), [portal](https://mosdac.gov.in/) |
| **NOAA GFS (NOMADS / AWS Open Data)** | **Available; Planned** (public, heavy GRIB2) | None | AWS S3 `noaa-gfs-bdp-pds`, NOMADS | Future NWP / model map layers; **not** MVP | [AWS registry](https://registry.opendata.aws/noaa-gfs-bdp-pds/) |
| **IMD Open Data / data.gov.in datasets** | **Available; Planned** | None (public CSV, historical) | Historical rainfall/temperature datasets | Possible "climate info" demo extension | data.gov.in IMD datasets (verify dataset IDs in Phase 2) |
| **Open-Meteo geocoding** (`geocoding-api.open-meteo.com`) | **Verified live 2026-09-06** | None (keyless) | `GET /v1/search?name=..&count=..` → results with name/lat/lon/country_code/admin1 (state); results outside India filtered server-side preference | Forward geocoding for city search | [Open-Meteo docs](https://open-meteo.com/en/docs/geocoding-api) |
| **BigDataCloud reverse geocoding** (`api.bigdatacloud.net`) | **Verified live 2026-09-06** | None (keyless free tier) | `GET /data/reverse-geocode-client?latitude&longitude&localityLanguage=en` → city/locality/principalSubdivision/country | Reverse geocoding fallback (after offline nearest-city) | [BigDataCloud docs](https://www.bigdatacloud.com/docs/api/free-reverse-geocode-to-city-api) |

---

## 1. IMD API Management Platform — VERIFIED (2026-09-06)

**Official portal:** https://api.imd.gov.in/ · **Public API reference:** https://api.imd.gov.in/public/api_reference.html

### Verified endpoints (from the official API reference)

| Endpoint | Data | Notes |
|----------|------|-------|
| `GET /api/v1/cityforecast?id=<station>` | 7-day city forecast: max/min temp, rainfall, humidity, wind, sunrise/sunset, weather text | Station IDs via `cityforecast_mapping` |
| `GET /api/v1/cityforecastloc` | Same, with lat/lon | |
| `GET /api/v1/cityforecast_mapping` | Station ↔ ID ↔ location mapping | Seed our `cities`/`stations` tables |
| `GET /api/v1/current_wx?id=<station>` | Current observation: temp, humidity, wind (dir/speed), MSLP, weather code (WMO 01–99), 24h rain | |
| `GET /api/v1/districtwarning?id=<district>` | **Official district warnings, Day 1–5**, warning codes (heavy rain, heat wave, cold wave, fog, etc.) + **color codes (Red/Orange/Yellow/Green)** | Core alert source |
| `GET /api/v1/districtnowcast` / `stationnowcast` | Nowcast categories (rain rates, thunderstorms, lightning, dust storm) + color | |
| `GET /api/v1/districtrainfall` / `staterainfall` | Actual vs normal rainfall, departure %, category (LE/E/N/D/LD/NR/ND) | |
| `GET /api/v1/aws_data` (+ `aws_data_mapping`, `?sid=<state>`) | AWS/ARG automatic weather station observations | |
| Cyclone, Marine (port/sea/coastal/fisherman), Agromet, Radar, Lightning, NHAI highway, Sun/Moon APIs | Specialized products | Future demo extensions (e.g., cyclone track) |

### Critical access constraints — API key + IP whitelisting
- **API key is required.** A live probe on 2026-09-06 of `https://api.imd.gov.in/api/v1/current_wx` and `/api/v1/cityforecast?id=42182` returned `{"error":"API key missing"}`. The public API reference does **not** document the auth mechanism (header vs query param) or the application flow — both must be confirmed with IMD (`docs/IMD-ACCESS.md` has the checklist and test commands).
- IMD's pages additionally mention **IP whitelisting** ("For IP Whitelisting click here"), and the open-meteo GitHub issue (#887) independently confirms: *"User has to provide their public IP so that same could be whitelisted at our end."*
- IMD also requires: **proper attribution**, and **client-side caching** to reduce load.
- Support/escalation contacts are published on the APIs page (ISSD technical support + escalation matrix).
- **Action for the team:** request the key + whitelisting immediately (ideally through the SIH nodal channel since IMD is the problem-statement owner). Meanwhile, all code paths run against the **provider interface** with Open-Meteo as fallback, so access is a config change, not a rework.

---

## 2. Open-Meteo — VERIFIED (2026-09-06)

- Free, open-source, **no API key**, free for non-commercial use; serves forecasts from national models (GFS-based among others), plus geocoding and historical APIs.
- Role in MVP: **resilience/fallback** for point forecasts (current + hourly/daily), **geocoding** for city search, and the *only* weather source until the IMD whitelist is granted.
- Caveat: it is **not IMD data**. Whether its global alert feed includes IMD-issued warnings is **not confirmed** — do not rely on it for official warnings; official warnings come from the IMD warning API / SACHET feed.

---

## 3. SACHET / NDMA CAP Feed — VERIFIED LIVE (2026-09-06)

Portal: https://sachet.ndma.gov.in/ ("1st and only portal across India to publish official warnings"; operated with C-DOT). The `/CapFeed` page is a Next.js SPA; the real endpoints were located by reading the app's own bundles and the official integration guide, then **probed live** — every claim below was confirmed with an actual request on 2026-09-06.

### Verified endpoints

| Endpoint | Method | Purpose | Verified behaviour |
|----------|--------|---------|--------------------|
| `cap_public_website/rss/rss_india.xml` | GET | All-India CAP/RSS feed index — one `<item>` per alert (guid, title, category, author=issuing agency, pubDate, detail link) | `200` + `ETag` + `Last-Modified`; state feeds at `rss/rss_<state>.xml` (state IDs observed in app bundle: 1000 All-India, 1287 Andaman, 1288 AP, 1290 Assam, 1291 Bihar, 1292 Chandigarh, 1293 Chhattisgarh, 1294 Dadra, 1296 Delhi, 1297 Goa, 1298 Gujarat, …) |
| `cap_public_website/FetchXMLFile?identifier=<guid>` | GET | Full CAP 1.2 alert (event, severity, urgency, certainty, headline, description, instruction, area, polygon URL) | Real flood alert captured (Assam-SDMA, severity Moderate). **Gotcha:** an unknown identifier returns HTTP 200 with an HTML 404 body — parsers must fail on content, not status. |
| `cap_public_website/FetchLocationWiseAlerts?lat&long&radius` | POST (query-encoded; JSON body → 400) | Location-scoped alerts — the portal's own app uses this | `{"alerts":[],"responseMessage":"Success"}` at Kolkata on 2026-09-06 (no active alerts) |
| `cap_public_website/GetWeatherInfo?lat&lng` | POST (query-encoded) | Location weather (Kolkata-Alipore station data seen: temp/feels-like/condition/hourly) | Works live; **secondary** source — not used for MVP weather (IMD/Open-Meteo are primary) |

### Mandatory caching (from the official Integration Guide for Agencies)

The guide (`https://sachet.ndma.gov.in/docs/Integration_Guide_For_Agencies.pdf`, 3 pages, public) requires **ETag-based client caching**: store the `ETag` header, send `If-None-Match` on every later poll, and on `304 Not Modified` reuse the cached copy — do not re-download. Verified live: a second request with the stored ETag returns `304`. This is implemented in `backend/app/providers/alerts/sachet.py`.

### Role in MVP

Secondary source of **official disaster warnings** (alerts pass through untouched — severity/urgency are never altered) and do's/don'ts context for the advisory KB. Area geometry: alerts expose area descriptions + a separate polygon URL (`FetchPolygonXMLFile`) — polygons land with the map phase.

---

## 4. MOSDAC (ISRO/SAC) — VERIFIED (2026-09-06)

- Portal: https://mosdac.gov.in/ — satellite (INSAT) & oceanographic data archive.
- **MOSDAC Data Download API** is a **bulk download tool**, not a real-time REST API: Python script (`mdapi.py`) + `config.json`; **MOSDAC account required** (registration + approval); username/password auth; **5,000 files/day cap**; search works without login, download does not.
- Role: **Future scope** — satellite imagery layers (e.g., cyclone), optional SIH demo extension. Not part of MVP core.

---

## 5. NOAA GFS — VERIFIED (2026-09-06)

- Public and free via AWS Open Data (`s3://noaa-gfs-bdp-pds`, 0.25°/0.5° grids, trailing ~30 days) and NOMADS.
- Role: **Planned** — future model-output map layers. Raw GRIB ingestion is out of MVP scope (Open-Meteo already provides GFS-derived point forecasts).

---

## Rule of engagement (from the brief, now codified)

1. Never invent an endpoint, field, key, or integration status. This matrix is the single source of truth; update it whenever a new source is proposed.
2. Every provider integration ships with **fixture tests** from captured real responses (sanitized), so the pipeline is testable even when the live source is down or not yet authorized.
3. When a source is unavailable at request time, the response says so explicitly and shows the last-known-good data with its timestamp — never silence, never invention.