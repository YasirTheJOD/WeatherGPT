"""Seed file sanity checks — catch bad curated data before it ships."""

import json

from app.services.location.alias_index import AliasIndex, normalize
from tests.conftest import DATA_DIR


def test_cities_seed_is_valid_and_complete():
    records = json.loads((DATA_DIR / "cities_seed.json").read_text(encoding="utf-8"))
    assert isinstance(records, list)
    assert len(records) >= 20
    for record in records:
        assert record.get("name"), f"missing name: {record}"
        assert isinstance(record.get("latitude"), (int, float)), record
        assert isinstance(record.get("longitude"), (int, float)), record
        assert isinstance(record.get("aliases", []), list), record


def test_cities_seed_has_no_duplicate_names():
    records = json.loads((DATA_DIR / "cities_seed.json").read_text(encoding="utf-8"))
    names = [normalize(r["name"]) for r in records]
    assert len(names) == len(set(names)), "duplicate canonical city names"


def test_stations_sample_is_valid():
    data = json.loads((DATA_DIR / "stations_sample.json").read_text(encoding="utf-8"))
    assert data["_note"].startswith("SYNTHETIC"), "sample file must stay labelled"
    for station in data["stations"]:
        assert station["Station_Code"].startswith("SMPL"), "sample codes must be clearly fake"
        assert isinstance(station["Latitude"], (int, float))


def test_alias_index_loads_from_seed():
    index = AliasIndex.load_seed(DATA_DIR / "cities_seed.json")
    assert len(index.candidates) >= 20


# ---------------------------------------------------------------------------
# Devanagari aliases — the Hindi/voice path (ARCHITECTURE §10 scenario 5)
# ---------------------------------------------------------------------------
#
# A Devanagari place name cannot fall through to the geocoder: Open-Meteo
# Geocoding is searched in Latin script, so "दिल्ली" returns nothing. The
# curated alias index is therefore the only thing that can resolve it, which is
# exactly what its docstring says it is for ("Hinglish spellings, regional
# names").
#
# `normalize()` strips NFD combining marks, so Devanagari matras are folded away
# ("दिल्ली" -> "दिलल") identically on the seed and query side — matching still
# works, but two different names *could* fold together. That would silently
# resolve one city as another, so the collision test below is the real guard.

DEVANAGARI_CITIES = [
    "Kolkata",
    "Delhi",
    "Mumbai",
    "Chennai",
    "Bengaluru",
    "Hyderabad",
    "Pune",
    "Jaipur",
    "Lucknow",
    "Bhopal",
]


def _records() -> list[dict]:
    return json.loads((DATA_DIR / "cities_seed.json").read_text(encoding="utf-8"))


def _devanagari(value: str) -> bool:
    return any("\u0900" <= ch <= "\u097f" for ch in value)


def test_major_cities_carry_devanagari_aliases():
    by_name = {r["name"]: r for r in _records()}
    missing = [n for n in DEVANAGARI_CITIES if not any(map(_devanagari, by_name[n].get("aliases", [])))]
    assert not missing, f"no Devanagari alias for: {missing}"


def test_no_alias_folds_onto_another_city():
    """No two cities may share a normalized alias key."""
    owners: dict[str, set[str]] = {}
    for record in _records():
        for alias in [record["name"], *record.get("aliases", [])]:
            owners.setdefault(normalize(alias), set()).add(record["name"])
    collisions = {key: names for key, names in owners.items() if len(names) > 1}
    assert not collisions, f"alias keys map to multiple cities: {collisions}"


def test_every_alias_resolves_to_its_own_city():
    """Includes the Devanagari matra folding: an alias must never drift."""
    index = AliasIndex.load_seed(DATA_DIR / "cities_seed.json")
    wrong: list[tuple[str, str, list[str]]] = []
    for record in _records():
        for alias in record.get("aliases", []):
            hits = index.lookup(alias)
            if not hits or hits[0].name != record["name"]:
                wrong.append((record["name"], alias, [h.name for h in hits[:2]]))
    assert not wrong, f"aliases resolving to the wrong city: {wrong}"


def test_devanagari_city_names_resolve_offline():
    index = AliasIndex.load_seed(DATA_DIR / "cities_seed.json")
    for query, expected in [("दिल्ली", "Delhi"), ("कोलकाता", "Kolkata"), ("मुंबई", "Mumbai")]:
        hits = index.lookup(query)
        assert hits and hits[0].name == expected, f"{query} -> {[h.name for h in hits]}"