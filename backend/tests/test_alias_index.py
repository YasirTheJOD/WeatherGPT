"""Alias index tests."""

from app.services.location.alias_index import AliasIndex, normalize
from tests.conftest import DATA_DIR


def _index() -> AliasIndex:
    return AliasIndex.load_seed(DATA_DIR / "cities_seed.json")


def test_normalize_handles_case_spaces_diacritics():
    assert normalize("  Bengaluru ") == "bengaluru"
    assert normalize("Bengalūru") == "bengaluru"  # diacritic stripped
    assert normalize("NEW DELHI") == "new delhi"


def test_exact_alias_match():
    index = _index()
    hits = index.lookup("calcutta")
    assert len(hits) == 1
    assert hits[0].name == "Kolkata"
    assert hits[0].confidence == 0.95
    assert hits[0].source == "aliases"


def test_exact_canonical_match():
    index = _index()
    hits = index.lookup("mumbai")
    assert len(hits) == 1
    assert hits[0].name == "Mumbai"


def test_substring_match_lower_confidence():
    index = _index()
    hits = index.lookup("bengal")
    assert any(h.name == "Bengaluru" and h.confidence == 0.8 for h in hits)


def test_unknown_query_returns_empty():
    index = _index()
    assert index.lookup("zzz-not-a-city") == []


def test_nearest_city_offline():
    index = _index()
    nearest = index.nearest(22.57, 88.36)  # Kolkata coords
    assert nearest is not None
    assert nearest.name == "Kolkata"
    # Far away -> None
    assert index.nearest(-33.8, 151.2) is None