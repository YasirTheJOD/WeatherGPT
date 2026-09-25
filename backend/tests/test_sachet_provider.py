"""SACHET CAP provider tests — fixtures are captured real responses."""

import httpx
import pytest

from app.core.config import Settings
from app.providers.alerts.sachet import SachetAlertProvider, parse_cap, parse_rss
from tests.conftest import load_text


def _provider(handler) -> SachetAlertProvider:
    settings = Settings()
    transport = httpx.MockTransport(handler=handler)
    return SachetAlertProvider(
        settings, client=httpx.AsyncClient(transport=transport, base_url=settings.sachet_base_url)
    )


# --- parsers ----------------------------------------------------------------


def test_parse_rss_real_trimmed_feed():
    alerts = parse_rss(load_text("sachet_rss_trimmed.xml"))
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.identifier == "1788712414336010"
    assert "Thunderstorms" in alert.title
    assert "IMD Guwahati" in alert.author
    assert alert.category == "Met"
    assert alert.published_at is not None
    assert alert.detail_url.endswith("FetchXMLFile?identifier=1788712414336010")
    assert alert.provenance.authoritative is True


def test_parse_cap_real_flood_alert():
    alert = parse_cap(load_text("sachet_cap_flood.xml"))
    assert alert.identifier == "IN-1788711107401010_10"
    assert alert.sender == "Assam-SDMA"
    assert alert.status == "Actual"
    assert alert.msg_type == "Update"
    assert alert.event == "Flood"
    assert alert.category == "Met"
    assert alert.severity == "Moderate"
    assert alert.urgency == "Future"
    assert alert.certainty == "Likely"
    assert alert.sent_at is not None
    assert alert.expires_at is not None
    assert "Dhansiri" in alert.headline
    assert "Danger Level" in alert.description
    assert alert.areas[0].area_desc == "Dhansiri (S), Golaghat, Golaghat, Assam"
    assert alert.polygon_url.endswith("FetchPolygonXMLFile?identifier=1788711107401010")


# --- provider behaviour -----------------------------------------------------


async def test_fetch_feed_parses_and_returns_etag():
    def handler(request):
        return httpx.Response(
            200,
            headers={"etag": '"v1"'},
            text=load_text("sachet_rss_trimmed.xml"),
        )

    provider = _provider(handler)
    result = await provider.fetch_feed()
    assert result.modified is True
    assert result.etag == '"v1"'
    assert len(result.alerts) == 1


async def test_fetch_feed_304_means_not_modified():
    provider = _provider(lambda request: httpx.Response(304))
    result = await provider.fetch_feed(etag='"v1"')
    assert result.modified is False
    assert result.etag == '"v1"'
    assert result.alerts == []


async def test_fetch_feed_error_status_is_unavailable():
    from app.providers.base import ProviderUnavailable

    provider = _provider(lambda request: httpx.Response(500))
    with pytest.raises(ProviderUnavailable, match="HTTP 500"):
        await provider.fetch_feed()


async def test_fetch_alert_detail_parses_cap():
    def handler(request):
        return httpx.Response(200, text=load_text("sachet_cap_flood.xml"))

    provider = _provider(handler)
    alert = await provider.fetch_alert_detail("1788711107401010")
    assert alert.event == "Flood"
    assert alert.severity == "Moderate"


async def test_fetch_nearby_empty_result():
    provider = _provider(
        lambda request: httpx.Response(200, json={"alerts": [], "responseMessage": "Success"})
    )
    alerts = await provider.fetch_nearby(22.57, 88.36)
    assert alerts == []