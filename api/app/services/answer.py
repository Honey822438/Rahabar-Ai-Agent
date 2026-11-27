"""Turns a question into an AskResponse. This is where the query pipeline lives (section 3.2)."""

from __future__ import annotations

import logging
import time
import uuid

from ..config import Settings
from ..logjson import request_id_var
from ..providers.llm.base import LLMProvider
from ..retrieval.base import Retriever
from ..schemas import Answer, AskResponse, Passage, RetrievedRef
from . import guardrails, telemetry, tracing
from .cache import SemanticCache, skip_cache
from .grounding import ABSTENTION, FALLBACK, enforce_citations
from .prompt import build_messages

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


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 1)


def answer_question(
    question: str, retriever: Retriever, provider: LLMProvider, settings: Settings,
    cache: SemanticCache | None = None,
) -> AskResponse:
    request_id = request_id_var.get()
    if request_id == "-":            # called outside an HTTP request (eval suite, CLI)
        request_id = uuid.uuid4().hex
    telemetry.take_generation()
    started = time.perf_counter()
    latency: dict[str, float] = {}
    passages: list[Passage] = []
    raw: list[Passage] = []          # as retrieved, before the injection rail
    rails: list[dict[str, object]] = guardrails.screen_query(question)
    vector: list[float] | None = None
    generation: str | None = None
    hit: AskResponse | None = None
    used_fallback = False
    prompt: list[dict[str, str]] | None = None
    try:
        with telemetry.RETRIEVAL_SECONDS.time():
            t = time.perf_counter()
            vector = retriever.embed(question)
            latency["embed"] = _ms(t)
            t = time.perf_counter()
            generation, hit = _cache_lookup(cache, retriever, question, vector)
            latency["cache"] = _ms(t)
            if hit is None:
                t = time.perf_counter()
                raw = retriever.retrieve(question, k=settings.top_k, vector=vector)
                latency["retrieve"] = _ms(t)
                t = time.perf_counter()
                passages, dropped = guardrails.screen_passages(
                    raw, drop=settings.injection_rail != "off")
                rails += dropped
                latency["guardrail"] = _ms(t)
    except Exception as exc:  # embedding service or Chroma down: a safe reply, never a 500
        log.warning("retrieval failed", extra={"error": type(exc).__name__})
        answer, used_fallback = FALLBACK, True
        telemetry.FALLBACKS.inc()
    else:
        if hit is not None:
            answer = Answer(reasoning="", answer=hit.answer, citations=hit.citations,
                            answered_from_context=True, confidence=hit.confidence)
        elif not passages or max(p.score for p in passages) < settings.relevance_floor:
            # The model is never asked: it can't invent an answer from evidence it doesn't get.
            answer = ABSTENTION
        else:
            prompt = build_messages(question, passages)
            t = time.perf_counter()
            answer, used_fallback = _generate(question, passages, provider)
            latency["generate"] = _ms(t)
            answer = enforce_citations(answer, passages)
    latency["total"] = _ms(started)
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

    gen = telemetry.take_generation()
    _trace(question, settings, retriever, provider, request_id, raw, passages, rails, prompt,
           response, gen, latency, hit is not None, cache is not None and generation is not None,
           used_fallback, generation)
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
            "guardrails": [f"{g['action']}:{g['rail']}" for g in rails],
            **gen,
        },
    )
    return response


def _trace(question: str, settings: Settings, retriever: Retriever, provider: LLMProvider,
           request_id: str, raw: list[Passage], passages: list[Passage],
           rails: list[dict[str, object]], prompt: list[dict[str, str]] | None,
           response: AskResponse, gen: dict[str, object], latency: dict[str, float],
           cached: bool, cache_lookup: bool, fallback: bool, generation: str | None) -> None:
    """D1: everything needed to explain this answer later, as one record."""
    try:
        kept = {p.chunk_id for p in passages}
        filters: dict[str, object] = getattr(retriever, "filters", lambda q: {})(question)
        version = getattr(retriever, "embed_version", lambda: "n/a")()
        record = {
            "trace_id": request_id,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "query": question,
            "rewritten_query": None,        # no query rewriting in this pipeline
            "embedding": {"model": settings.embed_model, "version": version,
                          "query_prefix": "search_query: "
                          if settings.embed_model.startswith("nomic") else ""},
            "collection": settings.collection,
            "index_generation": generation,
            "filters": filters,
            "top_k": settings.top_k,
            "relevance_floor": settings.relevance_floor,
            "top1_score": round(max((p.score for p in raw), default=0.0), 4) if raw else None,
            "retrieved": [{"rank": i, "chunk_id": p.chunk_id, "doc_id": p.doc_id,
                           "doc_version": p.doc_version, "source": p.source,
                           "section": p.section, "page": p.page, "score": round(p.score, 4),
                           "boosted": p.boosted, "dropped": p.chunk_id not in kept}
                          for i, p in enumerate(raw, 1)],
            "reranked_order": [p.chunk_id for p in passages],
            "rerank": "exact-term boost (clause numbers, course codes) then cosine",
            "context": [p.model_dump(include={"chunk_id", "text", "source", "section",
                                              "page", "score"}) for p in passages]
            if prompt else [],
            "prompt_hash": tracing.prompt_hash(prompt) if prompt else None,
            "prompt": prompt,
            "llm": {"provider": provider.name, "model": gen.get("model", settings.llm_model),
                    "temperature": settings.temperature, "seed": settings.llm_seed or None,
                    "response_format": "json_object", "called": prompt is not None,
                    # which hosted target answered (gemini / groq) and what failed before it
                    "answered_by": "fallback" if fallback else gen.get("llm_target"),
                    "failed_over_from": gen.get("failed_over_from", []),
                    "tokens_in": gen.get("tokens_in"), "tokens_out": gen.get("tokens_out")},
            "response": {"answer": response.answer,
                         "answered_from_context": response.answered_from_context,
                         "confidence": response.confidence},
            "citations": [c.model_dump() for c in response.citations],
            "guardrails": rails,
            "abstained": not response.answered_from_context and not fallback,
            "fallback": fallback,
            "cached": cached,
            "cache_lookup": cache_lookup,
            "latency_ms": latency,
        }
        tracing.emit(record, settings.trace_file)
    except Exception as exc:  # tracing must never fail an answer
        log.warning("trace failed", extra={"error": type(exc).__name__})
