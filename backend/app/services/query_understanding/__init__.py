"""Query understanding — free-form input → typed QuerySpec.

Implemented (Phase 5): `QueryUnderstandingService` in `parser.py` — a
rules-first extractor covering intent, English/Hinglish/Devanagari location
extraction, time windows ("kal"/"tomorrow", "shaam"/"subah"), language
detection, and the "near me" current-location signal. An LLM-assisted parser
can replace it behind the same `parse()` contract.
"""

from app.services.query_understanding.parser import QueryUnderstandingService

__all__ = ["QueryUnderstandingService"]