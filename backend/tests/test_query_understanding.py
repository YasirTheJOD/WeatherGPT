"""Query understanding tests — rules-first English + Hinglish parsing."""

from app.domain.models import LocationCandidate
from app.services.query_understanding.parser import (
    QueryUnderstandingService,
    detect_intent,
    detect_language,
    extract_place,
)


def test_intent_priority_alerts_wins_over_forecast():
    assert detect_intent("heavy rain warning in Kolkata") == "alerts"
    assert detect_intent("what should i do about the alert") == "alerts"


def test_intent_forecast_vs_current():
    assert detect_intent("will it rain tomorrow in Mumbai") == "forecast"
    assert detect_intent("kal mumbai mein baarish hogi kya") == "forecast"
    assert detect_intent("what is the weather in Delhi") == "current_weather"


def test_language_detection():
    assert detect_language("what is the weather") == "en"
    assert detect_language("kal shaam mumbai mein baarish hogi kya") == "hinglish"
    assert detect_language("आज कोलकाता में मौसम कैसा है") == "hi"


def test_contractions_are_folded_before_place_extraction():
    """Regression: the demo's opening prompt is contracted.

    "What's the weather in Kolkata right now?" previously extracted
    "s kolkata" (the apostrophe became a space and "s" is not a stop word), so
    the headline scenario resolved nowhere.
    """
    assert extract_place("What's the weather in Kolkata right now?") == "kolkata"
    assert extract_place("What's the forecast for Mumbai tomorrow?") == "mumbai"
    assert extract_place("It's raining in Delhi") == "delhi"
    assert extract_place("That's the weather in Chennai") == "chennai"
    # Smart quotes appear whenever a prompt is pasted from a doc or chat.
    assert extract_place("What\u2019s the weather in Pune?") == "pune"


def test_extract_place_stops_words():
    assert extract_place("what is the weather in Kolkata right now") == "kolkata"
    assert extract_place("will it rain tomorrow in Mumbai") == "mumbai"
    assert extract_place("kal shaam mumbai mein baarish hogi kya") == "mumbai"
    assert extract_place("alerts near me") is None


def test_parse_english_weather_query():
    spec = QueryUnderstandingService().parse("What is the weather in Kolkata right now?")
    assert spec.intent == "current_weather"
    assert spec.place_query == "kolkata"
    assert spec.day_offset == 0
    assert spec.language == "en"


def test_parse_hinglish_forecast_window():
    spec = QueryUnderstandingService().parse("Kal shaam Mumbai mein baarish hogi kya?")
    assert spec.intent == "forecast"
    assert spec.place_query == "mumbai"
    assert spec.day_offset == 1  # kal = tomorrow
    assert spec.part_of_day == "evening"  # shaam
    assert spec.language == "hinglish"


def test_parse_near_me_signals_current_location():
    spec = QueryUnderstandingService().parse("any alerts near me?")
    assert spec.intent == "alerts"
    assert spec.wants_current_location is True
    assert spec.place_query is None


def test_parse_explicit_candidate_skips_extraction():
    candidate = LocationCandidate(
        name="Mumbai",
        state="Maharashtra",
        country_code="IN",
        latitude=19.07,
        longitude=72.87,
        source="aliases",
        confidence=0.9,
    )
    spec = QueryUnderstandingService().parse(
        "", candidate=candidate, explicit_intent="forecast"
    )
    assert spec.location == candidate
    assert spec.intent == "forecast"