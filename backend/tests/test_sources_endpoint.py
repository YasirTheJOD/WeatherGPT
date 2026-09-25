"""Source transparency endpoint tests (ARCHITECTURE §5, demo scenario 7)."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings


def _client(**overrides) -> TestClient:
    # rate limit off so the test never touches Redis.
    settings = Settings(rate_limit_enabled=False, **overrides)
    from app.main import create_app

    return TestClient(create_app(settings))


@pytest.fixture
def sources_client() -> TestClient:
    return _client(imd_api_key="")


def test_sources_lists_the_curated_registry(sources_client):
    response = sources_client.get("/api/v1/sources")
    assert response.status_code == 200
    body = response.json()
    ids = [s["source_id"] for s in body["sources"]]
    assert ids[:3] == ["imd", "open_meteo", "sachet"]
    assert {"mosdac", "noaa_gfs", "geocoding_open_meteo", "bigdatacloud"} <= set(ids)
    assert body["counts"]["total"] == len(body["sources"])
    assert body["counts"]["available"] == sum(
        1 for s in body["sources"] if s["available"]
    )
    assert body["generated_at"]


def test_imd_reports_unavailable_without_a_key(sources_client):
    sources = {s["source_id"]: s for s in sources_client.get("/api/v1/sources").json()["sources"]}
    imd = sources["imd"]
    assert imd["available"] is False
    assert imd["status"] == "requires_authorization"
    assert imd["official"] is True
    assert "IMD_API_KEY" in imd["available_message"]
    assert imd["evidence_url"]


def test_imd_flips_available_when_key_is_configured():
    client = _client(imd_api_key="test-key")
    sources = {s["source_id"]: s for s in client.get("/api/v1/sources").json()["sources"]}
    assert sources["imd"]["available"] is True
    assert sources["imd"]["available_message"] is None


def test_official_sources_are_flagged(sources_client):
    sources = {s["source_id"]: s for s in sources_client.get("/api/v1/sources").json()["sources"]}
    assert sources["sachet"]["official"] is True
    assert sources["open_meteo"]["official"] is False
    # Fallback LLM responder works with zero keys -> always available.
    assert sources["llm"]["available"] is True


def test_planned_sources_are_not_available(sources_client):
    sources = {s["source_id"]: s for s in sources_client.get("/api/v1/sources").json()["sources"]}
    assert sources["mosdac"]["available"] is False
    assert sources["noaa_gfs"]["status"] == "planned"


def test_unkeyed_llm_provider_reports_fallback_message():
    client = _client(llm_provider="groq", groq_api_key="")
    sources = {s["source_id"]: s for s in client.get("/api/v1/sources").json()["sources"]}
    assert sources["llm"]["available"] is False
    assert "no key" in sources["llm"]["available_message"]
