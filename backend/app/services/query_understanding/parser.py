"""Query understanding — free-form input → typed QuerySpec.

Rules first (regex + stop-word location extraction + time-word parsing);
LLM assist for messy/Hinglish inputs is a future extension behind the same
interface. This is the P4 "Query Understanding" stage of the pipeline.

Design notes:
  - Location extraction is stop-word subtraction: everything that is not a
    stop word in a weather sentence is assumed to be the place name. Mirrors
    the Phase 4 frontend router, with a fuller English + Hinglish vocabulary.
  - Intent is decided BEFORE location: official-warning keywords win over
    forecast words win over plain weather.
  - "kal"/"tomorrow" → day_offset=1, "shaam"/"evening" → part_of_day. These
    feed the responder's phrasing ("Tomorrow evening in Mumbai: …").
  - Language: Devanagari → "hi"; romanized-Hindi particles → "hinglish";
    otherwise "en". Recorded in the QuerySpec for the LLM prompt (the
    fallback responder answers in English, as the Phase 4 UI expects).
"""

from __future__ import annotations

import re

from app.domain.chat import QuerySpec
from app.domain.models import LocationCandidate

# Words that are part of a weather sentence, never part of a place name.
STOP_WORDS: frozenset[str] = frozenset(
    {
        # English
        "what", "whats", "what's", "is", "the", "in", "at", "current", "weather",
        "today", "now", "forecast", "tomorrow", "will", "it", "rain", "raining",
        "rains", "rainy", "alerts", "alert", "warning", "warnings", "for", "near",
        "me", "my", "area", "please", "show", "give", "tell", "about", "and",
        "of", "here", "right", "currently", "exactly", "how", "like", "do", "i",
        "should", "any", "there", "looks", "going", "be", "outside", "condition",
        "conditions", "temperature", "humidity", "wind", "pressure",
        # Contraction stems — the apostrophe is folded away before matching, so
        # "what's" -> "whats", "it's" -> "its", "that's" -> "thats".
        "its", "thats", "dont", "cant", "wont", "isnt", "arent", "heres",
        "theres",
        # Hinglish (romanized Hindi)
        "kya", "hai", "kal", "shaam", "subah", "baarish", "mausam", "ka", "ki",
        "ke", "mein", "me", "hoga", "hogi", "ho", "rahegi", "rahega", "aaj", "barish",
        "abhi", "ko", "se", "kyaa", "kya", "karun", "karna", "chetaavani",
        "suraksha", "raat", "dopahar", "sabah", "hona", "hogaya",
        # Romanized question words — never part of a place name
        "kaisa", "kaisi", "kaise", "kahan", "kahaan", "kab", "kitna", "kitni",
        "bata", "batao", "bataiye", "degree", "degrees",
        # Devanagari
        "क्या", "है", "कल", "शाम", "सुबह", "बारिश", "मौसम", "का", "की", "के",
        "में", "होगा", "होगी", "हो", "रहेगी", "रहेगा", "आज", "अभी", "को", "से",
        "चेतावनी", "सुरक्षा", "रात", "दोपहर",
        # Devanagari question words — never part of a place name
        "कैसा", "कैसी", "कैसे", "कहाँ", "कहां", "कब", "कितना", "कितनी",
        "बताओ", "बताइए",
    }
)

INTENT_ALERTS: tuple[str, ...] = (
    "alert", "alerts", "warning", "warnings", "चेतावनी", "chetaavani",
    "what to do", "what should i do", "should i do", "kya karun", "kya karu",
    "suraksha",
)
INTENT_FORECAST: tuple[str, ...] = (
    "forecast", "tomorrow", "kal", "predict", "baarish", "barish", "rain",
    "raining", "rains", "rainy", "mausam", "बारिश", "कल",
)
CURRENT_LOCATION_PHRASES: tuple[str, ...] = (
    "near me", "my area", "my location", "here", "yahan", "idhar", "यहाँ",
    "मेरे आसपास", "मेरे पास",
)

_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_ROMAN_HINDI_HINTS = frozenset(
    {"kya", "hai", "kal", "shaam", "subah", "baarish", "barish", "mausam",
     "hoga", "hogi", "rahegi", "rahega", "aaj", "abhi", "mein", "karun"}
)
# Apostrophes are *removed* (contraction folding), not treated as separators.
# "what's" must become "whats" (a stop word) — turning it into "what s" leaves a
# stray "s" that gets extracted as part of the place name.
_APOSTROPHE_RE = re.compile(r"['\u2019\u02bc`]")
_PUNCT_RE = re.compile(r"[^a-z0-9\s\u0900-\u097F]")

TIME_WORDS: dict[str, int] = {
    "kal": 1, "tomorrow": 1, "कल": 1,
    "aaj": 0, "today": 0, "आज": 0,
    "parson": 2, "day after tomorrow": 2, "परसों": 2,
}
PART_OF_DAY_WORDS: dict[str, str] = {
    "shaam": "evening", "evening": "evening", "raat": "evening", "night": "evening",
    "subah": "morning", "morning": "morning", "sabah": "morning",
    "शाम": "evening", "रात": "evening", "सुबह": "morning",
}


def detect_language(text: str) -> str:
    """'hi' for Devanagari, 'hinglish' for romanized Hindi, else 'en'."""
    lowered = text.lower()
    if _DEVANAGARI_RE.search(text):
        return "hi"
    words = set(re.findall(r"[a-z]+", lowered))
    if words & _ROMAN_HINDI_HINTS:
        return "hinglish"
    return "en"


def extract_place(text: str) -> str | None:
    """Everything that is not a stop word is the place name.

    Contractions are folded first: "What's the weather in Kolkata right now?"
    is the demo's opening prompt, and stripping the apostrophe as punctuation
    would leave a stray "s" in the place ("s kolkata") so it would resolve
    nowhere.
    """
    normalized = _APOSTROPHE_RE.sub("", text.lower())
    cleaned = _PUNCT_RE.sub(" ", normalized)
    words = [w for w in cleaned.split() if w and w not in STOP_WORDS]
    place = " ".join(words).strip()
    return place or None


def detect_intent(text: str) -> str:
    lowered = text.lower()
    if any(phrase in lowered for phrase in INTENT_ALERTS):
        return "alerts"
    if any(phrase in lowered for phrase in INTENT_FORECAST):
        return "forecast"
    return "current_weather"


class QueryUnderstandingService:
    """Stateless rules-first parser → QuerySpec. Swappable for an LLM-assisted
    parser later without touching the orchestrator."""

    def parse(
        self,
        message: str,
        *,
        language: str | None = None,
        candidate: LocationCandidate | None = None,
        explicit_intent: str | None = None,
    ) -> QuerySpec:
        text = (message or "").strip()
        detected_lang = language or detect_language(text)

        # Explicit picks (disambiguation follow-up / answerForLocation) win:
        # the place is already resolved, keep the caller's intent when given.
        if candidate is not None:
            return QuerySpec(
                intent=explicit_intent or detect_intent(text),
                location=candidate,
                language=detected_lang,
            )

        intent = explicit_intent or detect_intent(text)
        lowered = text.lower()
        wants_current = any(
            phrase in lowered for phrase in CURRENT_LOCATION_PHRASES
        )
        place_query = None if wants_current else extract_place(text)

        day_offset = 0
        part_of_day = None
        for word, offset in TIME_WORDS.items():
            if word in lowered:
                day_offset = offset
                break
        for word, part in PART_OF_DAY_WORDS.items():
            if word in lowered:
                part_of_day = part
                break

        return QuerySpec(
            intent=intent,
            place_query=place_query,
            wants_current_location=wants_current,
            day_offset=day_offset,
            part_of_day=part_of_day,
            language=detected_lang,
        )