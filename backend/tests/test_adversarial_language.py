"""Adversarial multilingual drills — Devanagari, Hinglish, mixed scripts.

Multilingual was the weakest parsing path: Hindi place extraction is
stop-word subtraction, so a missing question word silently becomes part of the
place name and the query resolves against the wrong (or no) location. These
tests pin the vocabulary the demo relies on ("कैसा", "कल", "शाम") so the gap
cannot reopen.
"""

from app.services.query_understanding.parser import (
    QueryUnderstandingService,
    detect_intent,
    detect_language,
    extract_place,
)

from tests.chat_stubs import EchoResolver, done_event, make_client, parse_sse

DEVA_WEATHER = "आज कोलकाता में मौसम कैसा है"
DEVA_FORECAST = "कल दिल्ली में बारिश होगी क्या"
DEVA_EVENING = "कल शाम मुंबई में बारिश होगी"
DEVA_ALERTS = "चेतावनी कोलकाता"


# --- language detection -----------------------------------------------------


def test_detects_script_and_romanized_hinglish():
    assert detect_language(DEVA_WEATHER) == "hi"
    assert detect_language("kal shaam mumbai mein baarish hogi kya") == "hinglish"
    assert detect_language("What is the weather in Kolkata?") == "en"


def test_mixed_script_prefers_devanagari():
    assert detect_language("Kal कल Mumbai mein baarish") == "hi"


# --- place extraction -------------------------------------------------------


def test_devanagari_question_word_is_not_part_of_the_place():
    assert extract_place(DEVA_WEATHER) == "कोलकाता"


def test_devanagari_honorifics_and_question_words_are_stop_words():
    assert extract_place("कहाँ है कोलकाता में मौसम") == "कोलकाता"
    assert extract_place("मौसम कैसी है दिल्ली की") == "दिल्ली"


def test_romanized_question_words_are_not_part_of_the_place():
    assert extract_place("mausam kaisa hai kolkata") == "kolkata"
    assert extract_place("kahan barish hogi mumbai mein") == "mumbai"


# --- intent + time windows --------------------------------------------------


def test_devanagari_intents():
    assert detect_intent(DEVA_ALERTS) == "alerts"
    assert detect_intent(DEVA_FORECAST) == "forecast"
    assert detect_intent(DEVA_WEATHER) == "current_weather"


def test_devanagari_kal_is_tomorrow():
    spec = QueryUnderstandingService().parse(DEVA_FORECAST)
    assert spec.intent == "forecast"
    assert spec.place_query == "दिल्ली"
    assert spec.day_offset == 1
    assert spec.language == "hi"


def test_devanagari_shaam_is_evening():
    spec = QueryUnderstandingService().parse(DEVA_EVENING)
    assert spec.place_query == "मुंबई"
    assert spec.day_offset == 1
    assert spec.part_of_day == "evening"


def test_devanagari_aaj_is_today():
    spec = QueryUnderstandingService().parse(DEVA_WEATHER)
    assert spec.day_offset == 0
    assert spec.part_of_day is None


def test_uppercase_hinglish_still_parses():
    spec = QueryUnderstandingService().parse("KAL SHAAM MUMBAI MEIN BAARISH HOGI KYA?")
    assert spec.intent == "forecast"
    assert spec.place_query == "mumbai"
    assert spec.day_offset == 1
    assert spec.part_of_day == "evening"


# --- end to end -------------------------------------------------------------


def test_devanagari_forecast_end_to_end_answers_the_right_day_and_place():
    client = make_client(resolver=EchoResolver())
    resp = client.post("/api/v1/chat", json={"message": DEVA_FORECAST})
    done = done_event(parse_sse(resp.text))

    assert done["intent"] == "forecast"
    assert done["location"]["name"] == "दिल्ली"
    assert "Tomorrow" in done["text"]          # कल = day 2
    assert "दिल्ली" in done["text"]
    assert done["provenance_check"]["verified"] is True


def test_devanagari_alerts_query_uses_the_alerts_path():
    client = make_client(resolver=EchoResolver())
    resp = client.post("/api/v1/chat", json={"message": DEVA_ALERTS})
    done = done_event(parse_sse(resp.text))

    assert done["intent"] == "alerts"
    assert done["location"]["name"] == "कोलकाता"
    assert "No official warnings" in done["text"]
