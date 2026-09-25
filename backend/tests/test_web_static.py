"""Single-origin deployment: the API can serve the built Flutter PWA itself.

`WEB_DIR` publishes the PWA and `/api` from one process, which is what makes a
single public URL possible (a tunnel, or a free host with one service). Two
things have to hold or the deployment looks healthy while being useless:

* the API must keep priority — `/api/v1/**` and `/docs` are not static files, and
* a client-side route (`/map`) must return the shell, not a 404, or a refresh on
  a deep link breaks the demo.

The default (no `WEB_DIR`) stays API-only, so nothing changes for the normal
`flutter run` dev flow.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings

SHELL = "<!doctype html><title>WeatherGPT</title>"


def _client(**overrides) -> TestClient:
    settings = Settings(rate_limit_enabled=False, **overrides)
    from app.main import create_app

    return TestClient(create_app(settings))


@pytest.fixture
def web_bundle(tmp_path):
    """A minimal stand-in for `flutter build web` output."""
    (tmp_path / "index.html").write_text(SHELL, encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "main.dart.js").write_text("// compiled", encoding="utf-8")
    return tmp_path


def test_without_web_dir_the_root_stays_the_operator_json():
    body = _client().get("/").json()
    assert body["service"] == "WeatherGPT"
    assert body["health"] == "/api/v1/health"


def test_web_dir_serves_the_pwa_shell_at_the_root(web_bundle):
    client = _client(web_dir=str(web_bundle))
    response = client.get("/")
    assert response.status_code == 200
    assert "WeatherGPT" in response.text
    assert "text/html" in response.headers["content-type"]


def test_web_dir_serves_assets(web_bundle):
    client = _client(web_dir=str(web_bundle))
    asset = client.get("/assets/main.dart.js")
    assert asset.status_code == 200
    assert asset.text == "// compiled"


def test_client_side_routes_fall_back_to_the_shell(web_bundle):
    client = _client(web_dir=str(web_bundle))
    for path in ("/map", "/chat", "/some/deep/link"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "WeatherGPT" in response.text, path


def test_the_api_and_docs_keep_priority_over_the_static_mount(web_bundle):
    client = _client(web_dir=str(web_bundle))
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/sources").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_a_missing_web_dir_degrades_to_api_only(tmp_path):
    """A typo'd path must not crash the app — and must not pretend to work."""
    client = _client(web_dir=str(tmp_path / "does-not-exist"))
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/").json()["service"] == "WeatherGPT"
