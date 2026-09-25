# WeatherGPT — Frontend (Phase 4)

Flutter web PWA for the WeatherGPT SIH 2026 prototype. Consumes the FastAPI
backend in `../backend` (see root `README.md` for the full project).

## Run

```bash
flutter run -d chrome --web-port=5173
```

Port `5173` is in the backend CORS allowlist. Point the app at a different
backend with:

```bash
flutter run -d chrome --web-port=5173 \
  --dart-define=API_BASE_URL=http://<host>:8000
```

## Layout

```
lib/
  main.dart / app.dart        # bootstrap, providers, l10n delegates, shell
  core/
    config/                   # API base URL (--dart-define)
    api/                      # typed HTTP client + error mapping
    theme/                    # Material 3 brand theme
    widgets/                  # shared widgets (placeholders, later source cards)
  models/                     # typed mirrors of backend/app/domain/models.py
  state/                      # AppState: selected location + language
  features/
    chat/  weather/  alerts/  map/   # tab screens (built step by step in Phase 4)
  l10n/                       # app_en.arb / app_hi.arb (gen-l10n)
```

## Phase 4 progress

- ✅ Step 1 Foundations — shell, API client, models, l10n scaffold (EN/HI)
- ✅ Step 2 Weather screen — location bar (search + GPS), current conditions,
  7-day forecast strip, source cards, validation warnings, error/retry
- ✅ Step 3 Alerts — OFFICIAL WARNING cards (severity colors, validity window,
  instruction, areas, provenance), new Alerts tab
- ✅ Step 4 Map — OSM tiles (flutter_map), location pin, official CAP alert
  geometry (circles/polygons) colored by severity, camera follows location
- ✅ Step 5 Chat — bubbles, grounded weather/forecast/alert cards, source
  attribution, disambiguation chips, follow-up suggestions, Hinglish routing
  (swappable ChatService; the `/chat` SSE adapter renders the answer as it
  streams, and falls back to the typed endpoints when the backend is down)
- ✅ Step 6 Voice (Web Speech STT/TTS) · ✅ Step 7 Language selector (EN/HI) ·
  ✅ Step 8 Sources drawer (live registry) + polish

## Tests

```bash
flutter analyze
flutter test
```