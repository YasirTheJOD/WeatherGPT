#!/usr/bin/env bash
# Build the **deployable** Flutter web bundle.
#
# Two things here are deliberate and easy to get wrong by hand:
#
#  1. `--dart-define=API_BASE_URL=` (empty) makes the app call whatever origin
#     served the page. The backend serves this bundle itself (WEB_DIR), so the
#     PWA and /api share one origin: no CORS, no API host baked into the bundle,
#     so the same artefact works behind a tunnel, a LAN address or a real domain
#     — and the deploy keeps working when the host's URL is not what we guessed.
#
#  2. `--web-resources-cdn` + deleting the local `canvaskit/` drops the bundle
#     from ~41 MB to ~4.6 MB, which is small enough to commit (the free host
#     builds from Git and never runs Flutter). CanvasKit is then fetched from
#     Google's gstatic CDN at page load — a runtime dependency worth knowing
#     about, and the same class of dependency as the API itself.
#
# Usage:  bash scripts/build_web.sh      (then commit frontend/build/web)
set -euo pipefail

cd "$(dirname "$0")/../frontend"

flutter build web --release --dart-define=API_BASE_URL= --web-resources-cdn

rm -rf build/web/canvaskit
find build/web -name '*.symbols' -delete

echo
echo "Bundle ready: $(du -sh build/web | cut -f1) in frontend/build/web"
echo "Commit it (the host builds from Git and does not run Flutter), then push."
