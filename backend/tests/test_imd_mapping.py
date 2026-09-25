"""IMD station mapping ingestion tests."""

import pytest

from app.providers.base import ProviderUnavailable
from app.services.location.imd_mapping import IMDMappingLoader, parse_mapping
from tests.conftest import DATA_DIR, load_fixture


def test_parse_constructed_mapping():
    stations = parse_mapping(load_fixture("imd_cityforecast_mapping.json"))
    assert len(stations) == 4  # the missing-coordinates record is skipped
    by_code = {s.station_code: s for s in stations}
    assert by_code["42182"].name == "KOLKATA (ALIPORE)"
    assert by_code["42182"].state == "West Bengal"
    assert abs(by_code["42182"].latitude - 22.53) < 1e-6
    # variant key names (station_code/city/lat/lon) are tolerated
    assert by_code["42909"].name == "CHENNAI (MINAMBAKKAM)"
    assert by_code["42909"].longitude == 80.18


def test_parse_skips_records_without_coordinates():
    data = [
        {"Station_Code": "X1", "Station_Name": "No coords"},
        {"Station_Code": "X2", "Station_Name": "Bad coords", "Latitude": "abc", "Longitude": "12"},
    ]
    assert parse_mapping(data) == []


def test_parse_rejects_non_list_shape():
    with pytest.raises(ProviderUnavailable):
        parse_mapping({"unexpected": True})


def test_snapshot_load():
    stations = IMDMappingLoader.load_snapshot(DATA_DIR / "stations_sample.json")
    assert len(stations) == 3
    assert stations[0].station_code == "SMPL001"


async def test_build_index_falls_back_to_snapshot(settings_no_imd):
    loader = IMDMappingLoader(settings_no_imd)
    index = await loader.build_index(snapshot_path=DATA_DIR / "stations_sample.json")
    assert len(index) == 3
    nearest = index.nearest(22.57, 88.36)
    assert nearest is not None
    assert nearest.station_code == "SMPL001"


async def test_fetch_mapping_requires_key(settings_no_imd):
    loader = IMDMappingLoader(settings_no_imd)
    with pytest.raises(ProviderUnavailable, match="API key not configured"):
        await loader.fetch_mapping()