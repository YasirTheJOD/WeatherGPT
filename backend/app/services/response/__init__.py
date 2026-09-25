"""Response pipeline — grounded generation, provenance check, card assembly.

Implemented (Phase 5): the number-provenance post-check (`provenance.py`) —
every number in the answer must exist in the evidence bundle — and the reply
assembler (`assembler.py`) that merges LLM text with evidence cards,
suggestions and provenance into the typed ChatResponse the frontend renders.
"""

from app.services.response.assembler import assemble_chat_response
from app.services.response.provenance import check_provenance

__all__ = ["assemble_chat_response", "check_provenance"]