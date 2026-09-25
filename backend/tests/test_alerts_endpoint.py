"""Alerts endpoint tests — nearby alerts and the ETag caching flow."""

import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.providers.alerts.sachet import SachetAlertProvider
from tests.conftest import load_text


def _client_with_stubbed_sachet(handler) -> TestClient:
    from app.main import create_app

    settings = Settings()
    app = create_app(settings)
    app.state.alerts = SachetAlertProvider(
        settings,
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url=settings.sachet_base_url
        ),
    )
    app.state.sachet_etag = None
    return TestClient(app)


def test_nearby_alerts_returns_empty_list():
    def handler(request):
        return httpx.Response(200, json={"alerts": [], "responseMessage": "Success"})

    client = _client_with_stubbed_sachet(handler)
    response = client.get("/api/v1/alerts", params={"lat": 22.57, "lon": 88.36})
    assert response.status_code == 200
    body = response.json()
    assert body["alerts"] == []
    assert body["source"] == "sachet"


def test_feed_etag_caching_flow():
    calls = {"count": 0}

    def handler(request):
        calls["count"] += 1
        if request.headers.get("if-none-match"):
            return httpx.Response(304)
        return httpx.Response(
            200,
            headers={"etag": '"v1"'},
            text=load_text("sachet_rss_trimmed.xml"),
        )

    client = _client_with_stubbed_sachet(handler)

    first = client.get("/api/v1/alerts/feed")
    assert first.status_code == 200
    assert first.json()["modified"] is True
    assert first.json()["alert_count"] == 1
    assert first.json()["etag"] == '"v1"'

    # Second poll carries the stored ETag -> server answers 304 -> modified False.
    second = client.get("/api/v1/alerts/feed")
    assert second.status_code == 200
    assert second.json()["modified"] is False
    assert second.json()["alert_count"] == 0
    assert calls["count"] == 2