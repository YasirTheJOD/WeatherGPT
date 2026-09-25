# `data/` — station snapshot

| File | Status | Origin |
|------|--------|--------|
| `stations_sample.json` | **SYNTHETIC SAMPLE** | Hand-written dev fixture to exercise the IMD nearest-station code path. The `SMPL*` station codes and names are explicitly fake; only city coordinates are real. |
| `cities_seed.json` | **Curated seed** | ~40 major Indian cities with canonical names, Hinglish/regional/historical aliases (e.g. Calcutta→Kolkata, Bombay→Mumbai) and city-center coordinates. Coordinates are public knowledge; verify against the real `cityforecast_mapping` capture when the IMD key arrives. Extend freely — the alias index reads it directly. |

## When the IMD API key arrives

1. Follow `docs/IMD-ACCESS.md` step 3: capture `cityforecast_mapping` live.
2. Replace this file with the real capture (same `{"stations": [...]}` shape or the raw list — the parser tolerates both).
3. The loader prefers the live fetch over this file automatically; `/api/v1/health` and the app log will confirm which source was used.

Never present `stations_sample.json` as real IMD station data in demos or docs.