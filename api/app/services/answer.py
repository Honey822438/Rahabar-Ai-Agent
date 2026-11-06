"""Turns a question into an AskResponse. This is where the query pipeline lives (section 3.2)."""

from __future__ import annotations

import logging

from ..config import Settings
from ..logjson import request_id_var
from ..providers.llm.base import LLMProvider
from ..retrieval.base import Retriever
from ..schemas import Answer, AskResponse, Passage, RetrievedRef
from . import telemetry
from .cache import SemanticCache, skip_cache
from .grounding import ABSTENTION, FALLBACK, enforce_citations

log = logging.getLogger("rahbar.answer")

MAX_ATTEMPTS = 2  # the first try plus one retry


def _generate(question: str, passages: list[Passage], provider: LLMProvider) -> tuple[Answer, bool]:
    """Returns the answer and whether it is the fallback. Never raises: a user must not see
    a 500 because the model wrote prose instead of JSON, or the provider was down."""
    with telemetry.GENERATION_SECONDS.time():
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return provider.generate(question, passages), False
            except Exception as exc:  # invalid JSON, schema failure, timeout, rate limit
                # Only the type: provider errors can echo request details.
                log.warning("generation failed, will retry" if attempt < MAX_ATTEMPTS
                            else "generation failed, using the fallback",
                            extra={"attempt": attempt, "error": type(exc).__name__})
    telemetry.FALLBACKS.inc()
    return FALLBACK, True


def _cache_lookup(
    cache: SemanticCache | None, retriever: Retriever, question: str, vector: list[float]
) -> tuple[str | None, AskResponse | None]:
    """The generation to store under (None if the cache is off for this request) and any hit."""
    if cache is None or skip_cache(question):
        return None, None
    try:
        generation = str(retriever.index_metadata().get("index_generation", ""))
        cache.invalidate_if_reindexed(generation)
        hit = cache.lookup(generation, vector)
    except Exception as exc:  # the cache is an optimisation; its failure must not fail the answer
        log.warning("cache unavailable", extra={"error": type(exc).__name__})
        return None, None
    telemetry.record_cache_lookup(hit is not None)
    return generation, hit


def _remember(
    cache: SemanticCache | None, generation: str | None, question: str, vector: list[float] | None,
    response: AskResponse, safe_to_cache: bool,
) -> None:
    if cache is None:
        return
    try:
        cache.store_turn(question, response)
        if safe_to_cache and generation and vector is not None:
            cache.store(generation, question, vector, response)
    except Exception as exc:
        log.warning("cache write failed", extra={"error": type(exc).__name__})


def answer_question(
    question: str, retriever: Retriever, provider: LLMProvider, settings: Settings,
    cache: SemanticCache | None = None,
) -> AskResponse:
    request_id = request_id_var.get()
    telemetry.take_generation()
    passages: list[Passage] = []
    vector: list[float] | None = None
    generation: str | None = None
    hit: AskResponse | None = None
    used_fallback = False
    try:
        with telemetry.RETRIEVAL_SECONDS.time():
            vector = retriever.embed(question)
            generation, hit = _cache_lookup(cache, retriever, question, vector)
            if hit is None:
                passages = retriever.retrieve(question, k=settings.top_k, vector=vector)
    except Exception as exc:  # embedding service or Chroma down: a safe reply, never a 500
        log.warning("retrieval failed", extra={"error": type(exc).__name__})
        answer, used_fallback = FALLBACK, True
        telemetry.FALLBACKS.inc()
    else:
        if hit is not None:
            answer = Answer(reasoning="", answer=hit.answer, citations=hit.citations,
                            answered_from_context=True, confidence=hit.confidence)
        elif not passages or passages[0].score < settings.relevance_floor:
            # The model is never asked: it can't invent an answer from evidence it doesn't get.
            answer = ABSTENTION
        else:
            answer, used_fallback = _generate(question, passages, provider)
            answer = enforce_citations(answer, passages)

    if hit is not None:
        response = hit.model_copy(update={"request_id": request_id, "cached": True})
    else:
        response = AskResponse(
            request_id=request_id,
            answer=answer.answer,
            citations=answer.citations,
            answered_from_context=answer.answered_from_context,
            confidence=answer.confidence,
            retrieved=[
                RetrievedRef(chunk_id=p.chunk_id, source=p.source, section=p.section, page=p.page,
                             score=p.score)
                for p in passages
            ],
            provider=provider.name,
        )
    if not response.answered_from_context and not used_fallback:
        telemetry.ABSTENTIONS.inc()

    # Abstentions, out-of-scope answers and failed validations never reach the cache.
    safe_to_cache = hit is None and response.answered_from_context and not used_fallback
    _remember(cache, generation, question, vector, response, safe_to_cache)

    log.info(
        "answered",
        extra={
            "retriever": retriever.name,
            "provider": provider.name,
            "top_k": settings.top_k,
            "chunk_ids": [ref.chunk_id for ref in response.retrieved],
            "scores": [round(ref.score, 4) for ref in response.retrieved],
            "answered_from_context": response.answered_from_context,
            "abstained": not response.answered_from_context and not used_fallback,
            "cached": response.cached,
            "fallback": used_fallback,
            **telemetry.take_generation(),
        },
    )
    return response
