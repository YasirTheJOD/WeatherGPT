"""Weather endpoint tests — the provider chain, exercised via the API."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.providers.base import ProviderRegistry
from app.providers.weather.imd import IMDProvider
from app.providers.weather.open_meteo import OpenMeteoProvider
from tests.conftest import load_fixture


def _client_with_stubbed_open_meteo() -> TestClient:
    """App where IMD is unconfigured and Open-Meteo returns the captured fixture."""
    from app.main import create_app

    settings = Settings(imd_api_key="")
    transport = httpx.MockTransport(
        handler=lambda req: httpx.Response(200, json=load_fixture("open_meteo_current.json"))
    )
    om = OpenMeteoProvider(
        settings,
        client=httpx.AsyncClient(transport=transport, base_url=settings.open_meteo_base_url),
    )
    app = create_app(settings)
    app.state.registry = ProviderRegistry([IMDProvider(settings), om])
    return TestClient(app)


def test_current_weather_falls_back_to_open_meteo():
    client = _client_with_stubbed_open_meteo()
    response = client.get("/api/v1/weather/current", params={"lat": 22.57, "lon": 88.36})
    assert response.status_code == 200
    body = response.json()
    assert body["provider_used"] == "open-meteo"
    assert body["observation"]["temperature_c"] == 28.4
    assert body["observation"]["provenance"]["authoritative"] is False
    assert body["validation"]["valid"] is True


def test_all_providers_unavailable_returns_503(settings_no_imd):
    from app.main import create_app

    # Registry with only the unconfigured IMD provider -> nothing can serve.
    app = create_app(settings_no_imd)
    app.state.registry = ProviderRegistry([IMDProvider(settings_no_imd)])
    client = TestClient(app)

    response = client.get("/api/v1/weather/current", params={"lat": 22.57, "lon": 88.36})
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "imd" in detail["message"]
    assert "no provider" in detail["message"] or "configured" in detail["message"]