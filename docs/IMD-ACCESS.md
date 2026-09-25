# IMD API Access — Application Checklist

> Status: **Requires authorization.** Verified 2026-09-06 by probing the live endpoints from our machine.
> Owner: Lead (this doc) · Update this file as each step completes.

## Verified facts (2026-09-06)

1. **An API key is required.** Live probes returned:
   ```
   $ curl -s 'https://api.imd.gov.in/api/v1/current_wx'
   {"error":"API key missing"}
   $ curl -s 'https://api.imd.gov.in/api/v1/cityforecast?id=42182'
   {"error":"API key missing"}
   ```
2. **The public API reference does not document the auth mechanism** (header vs query param) or the key application flow. Both must be confirmed with IMD.
3. IMD's own pages additionally mention **IP whitelisting** ("For IP Whitelisting click here" on `mausam.imd.gov.in/responsive/apis.php`) and require **attribution** and **client-side caching**.
4. Public endpoint reference (authoritative): `https://api.imd.gov.in/public/api_reference.html`

## Checklist

- [ ] **1. Request the API key**
      - Channel: IMD APIs portal / the SIH nodal contact for this problem statement (IMD is the problem-statement owner — use that relationship; mention the SIH 2026 prototype and demo dates).
      - Include: team (United India), organization (IMD/MoES — SIH participant), purpose (authorized prototype + demo), expected call volume (prototype: low), and the **public IP** of the demo server for whitelisting.
- [ ] **2. Confirm the auth mechanism**
      - Test both (one will work; update `backend/app/providers/weather/imd.py` headers/params accordingly):
      ```bash
      curl -s 'https://api.imd.gov.in/api/v1/current_wx' -H 'X-API-Key: YOUR_KEY'
      curl -s 'https://api.imd.gov.in/api/v1/current_wx?key=YOUR_KEY'
      ```
- [ ] **3. Verify key + whitelist with the endpoints we use**
      ```bash
      curl -s 'https://api.imd.gov.in/api/v1/current_wx'        -H 'X-API-Key: YOUR_KEY'   # current obs
      curl -s 'https://api.imd.gov.in/api/v1/cityforecast?id=42182' -H 'X-API-Key: YOUR_KEY'   # 7-day city forecast
      curl -s 'https://api.imd.gov.in/api/v1/cityforecast_mapping'  -H 'X-API-Key: YOUR_KEY'   # station seed data
      curl -s 'https://api.imd.gov.in/api/v1/districtwarning?id=573' -H 'X-API-Key: YOUR_KEY'  # district warnings
      ```
- [ ] **4. Confirm rate limits / caching guidance** — IMD requires client-side caching; we already cache with TTLs (obs 5 min, forecasts 30 min). Ask for their guidance and adjust.
- [ ] **5. Capture real fixtures** — replace `backend/fixtures/imd_*.json` (currently constructed from the documented schema — see `backend/fixtures/README.md`) with sanitized real responses from step 3.
- [ ] **6. Attribution** — add the required IMD attribution string to the frontend (Phase 6) and the source cards.
- [ ] **7. Update this repo** — set `IMD_API_KEY` in `.env`, mark IMD row in `docs/DATA-SOURCES.md` as **Implemented** (or the accurate status), and confirm `/api/v1/health` reports `imd.available: true`.

## Until the key arrives

The demo runs fully on the Open-Meteo fallback (same interfaces, same provenance model, clearly labelled `authoritative: false`). The IMD key is a config change, not a rework.

## Contacts (published on IMD's APIs page — verify currency before use)

- Support: ISSD Technical Support (email on `mausam.imd.gov.in/responsive/apis.php`)
- Escalation: Sc-F contacts with phone/email published on the same page
- Portal: `https://api.imd.gov.in/` ("IMD API Management Platform")