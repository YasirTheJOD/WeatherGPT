# Test Fixtures — provenance

| File | Type | Origin |
|------|------|--------|
| `open_meteo_current.json` | **Captured real response** | Open-Meteo live call, Kolkata (22.57, 88.36), 2026-09-06 |
| `open_meteo_daily.json` | **Captured real response** | Open-Meteo live call, 7-day daily, Kolkata, 2026-09-06 |
| `imd_current_wx.json` | **Constructed** | Field schema from the official IMD API reference (`https://api.imd.gov.in/public/api_reference.html`), 2026-09-06. NOT a real observation. |
| `imd_cityforecast.json` | **Constructed** | Field schema from the official IMD API reference, 2026-09-06. NOT a real forecast. |
| `imd_cityforecast_mapping.json` | **Constructed** | Station-record shape inferred from the official IMD API reference's naming conventions, 2026-09-06. NOT a real capture. Includes variant key names and a skip record to exercise the tolerant parser. |
| `sachet_rss_trimmed.xml` | **Captured real response** | SACHET all-India CAP feed (`cap_public_website/rss/rss_india.xml`), captured 2026-09-06, trimmed to channel + first item. |
| `sachet_cap_flood.xml` | **Captured real response** | SACHET CAP 1.2 alert via `FetchXMLFile?identifier=1788711107401010` (Assam-SDMA flood), 2026-09-06. |
| `sachet_location_alerts_empty.json` | **Captured real response** | SACHET `FetchLocationWiseAlerts` for Kolkata (22.57, 88.36), 2026-09-06 — no active alerts, so the fixture exercises the empty path. |
| `met_norway_kolkata_compact.json` | **Captured real response** | MET Norway Locationforecast 2.0 `compact`, Kolkata (22.57, 88.36), captured 2026-09-25 — trimmed to the 7 local (IST) days a `days=7` forecast uses, keeping both the hourly and the later 6-hourly portions of the series. |
| `open_meteo_geocoding_kolkata.json` | **Captured real response** | Open-Meteo geocoding search `name=Kolkata`, 2026-09-06. |
| `open_meteo_geocoding_ranipur.json` | **Captured real response** | Open-Meteo geocoding search `name=Ranipur`, 2026-09-06 — trimmed to 4 of 5+ results; exercises the India filter and ambiguity demo (Pakistan/Bangladesh matches present). |
| `bigdatacloud_reverse_kolkata.json` | **Captured real response** | BigDataCloud reverse geocode for (22.57, 88.36), 2026-09-06 — trimmed to fields the parser reads. |

## Rules

1. **Never present constructed fixtures as real data** in demos or docs — they exist only to test parsing against the documented schema until the IMD API key is granted.
2. When the IMD key arrives (see `docs/IMD-ACCESS.md`), **replace the constructed fixtures with captured real responses** using the verification commands in that doc.
3. Live-provider tests are gated behind `RUN_LIVE_TESTS=1` so the suite never depends on the network.