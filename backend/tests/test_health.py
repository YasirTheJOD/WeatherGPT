"""Health endpoint tests."""


def test_health_lists_providers(client_no_imd):
    response = client_no_imd.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    providers = {p["provider_id"]: p for p in body["providers"]}
    # IMD has no key configured -> fail closed; Open-Meteo is keyless -> ready.
    assert providers["imd"]["available"] is False
    assert "not configured" in providers["imd"]["message"]
    assert providers["open-meteo"]["available"] is True