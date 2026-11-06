"""Turns a question into an AskResponse. This is where the query pipeline lives.

The version below is the bare minimum that works with the stubs: retrieve,
generate, return. Section 3.2 lists eight steps; this file does two of them.
"""

from __future__ import annotations

import logging

from ..config import Settings
from ..logjson import request_id_var
from ..providers.llm.base import LLMProvider
from ..retrieval.base import Retriever
from ..schemas import Answer, AskResponse, Citation, Passage, RetrievedRef
from .grounding import ABSTENTION, FALLBACK, enforce_citations

log = logging.getLogger("rahbar.answer")

MAX_ATTEMPTS = 2  # the first try plus one retry


def _generate(question: str, passages: list[Passage], provider: LLMProvider) -> tuple[Answer, bool]:
    """Returns the answer and whether it is the fallback. Never raises: a user must not see
    a 500 because the model wrote prose instead of JSON, or the provider was down."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return provider.generate(question, passages), False
        except Exception as exc:  # invalid JSON, schema failure, timeout, rate limit
            # Only the type: provider errors can echo request details.
            log.warning("generation failed", extra={"attempt": attempt,
                                                    "error": type(exc).__name__})
    return FALLBACK, True


def answer_question(
    question: str, retriever: Retriever, provider: LLMProvider, settings: Settings
) -> AskResponse:
    passages = retriever.retrieve(question, k=settings.top_k)
    used_fallback = False
    if not passages or passages[0].score < settings.relevance_floor:
        # The model is never asked: it can't invent an answer from evidence it doesn't get.
        answer = ABSTENTION
    else:
        answer, used_fallback = _generate(question, passages, provider)
        answer = enforce_citations(answer, passages)

    log.info(
        "answered",
        extra={
            "retriever": retriever.name,
            "provider": provider.name,
            "top_k": settings.top_k,
            "chunk_ids": [p.chunk_id for p in passages],
            "scores": [round(p.score, 4) for p in passages],
            "answered_from_context": answer.answered_from_context,
            "fallback": used_fallback,
        },
    )
    citations: list[Citation] = answer.citations
    return AskResponse(
        request_id=request_id_var.get(),
        answer=answer.answer,
        citations=citations,
        answered_from_context=answer.answered_from_context,
        confidence=answer.confidence,
        retrieved=[
            RetrievedRef(
                chunk_id=p.chunk_id, source=p.source, section=p.section, page=p.page, score=p.score
            )
            for p in passages
        ],
        provider=provider.name,
    )
