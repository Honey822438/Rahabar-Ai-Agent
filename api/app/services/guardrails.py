"""Prompt-injection rails (A3 D4). Every action they take is written to the request's trace.

Two rails, both pattern based (cheap, deterministic, explainable in a trace):
  query_injection      the user's question tries to override the instructions -> FLAGGED.
                       The question is still answered: the prompt treats it as data (rule 3),
                       and the flag shows up in monitoring (D3 "injection attempts").
  retrieval_injection  a retrieved chunk carries instructions to the model (an indirect
                       injection planted in a document, e.g. Batch B's library notice) ->
                       the chunk is DROPPED before the prompt is built, so the model never
                       sees it. The rest of the evidence is used as usual.
INJECTION_RAIL=off disables dropping (chunks are only flagged), for an A/B demonstration.
"""

from __future__ import annotations

import re
from typing import Any

from ..schemas import Passage

PATTERNS = [
    ("ignore_instructions", r"\b(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|the\s+)?"
                            r"(?:previous|prior|above|earlier|your)\s+(?:instructions|rules|prompts?)"),
    ("role_change", r"\byou\s+are\s+now\b|\bact\s+as\b|\bmaintenance\s+mode\b|\bdeveloper\s+mode\b"),
    ("prompt_exfiltration", r"\b(?:print|reveal|show|repeat|output)\s+(?:your\s+|the\s+)?"
                            r"(?:full\s+|entire\s+)?(?:system\s+prompt|instructions)\b"),
    ("fake_system_note", r"\b(?:system\s+note|system\s+message|important\s+system)\b"),
    ("forced_output", r"\btell\s+every\s+(?:user|student)\b|\balways\s+(?:say|answer|reply)\b"),
]
_COMPILED = [(name, re.compile(rx, re.IGNORECASE)) for name, rx in PATTERNS]


def detect(text: str) -> list[str]:
    """Names of the injection patterns found in text."""
    return [name for name, rx in _COMPILED if rx.search(text)]


def screen_query(question: str) -> list[dict[str, Any]]:
    hits = detect(question)
    return [{"rail": "query_injection", "action": "flagged", "patterns": hits}] if hits else []


def screen_passages(passages: list[Passage], drop: bool = True
                    ) -> tuple[list[Passage], list[dict[str, Any]]]:
    kept: list[Passage] = []
    actions: list[dict[str, Any]] = []
    for p in passages:
        hits = detect(p.text)
        if not hits:
            kept.append(p)
            continue
        actions.append({"rail": "retrieval_injection", "action": "dropped" if drop else "flagged",
                        "chunk_id": p.chunk_id, "doc_id": p.doc_id, "source": p.source,
                        "patterns": hits})
        if not drop:
            kept.append(p)
    return kept, actions
