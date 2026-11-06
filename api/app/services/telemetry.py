"""Pipeline metrics, and what the provider reports back for the per-request log line."""

from __future__ import annotations

from contextvars import ContextVar

from prometheus_client import Counter, Gauge, Histogram

_BUCKETS = (0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30)
RETRIEVAL_SECONDS = Histogram("rahbar_retrieval_seconds", "Embed and retrieve", buckets=_BUCKETS)
GENERATION_SECONDS = Histogram("rahbar_generation_seconds", "LLM generation", buckets=_BUCKETS)
CACHE_LOOKUPS = Counter("rahbar_cache_lookups_total", "Semantic cache lookups", ["result"])
CACHE_HIT_RATIO = Gauge("rahbar_cache_hit_ratio", "Hits / lookups since this process started")
ABSTENTIONS = Counter("rahbar_abstentions_total", "Answers declined as not covered")
FALLBACKS = Counter("rahbar_fallbacks_total", "Canned replies after failed generation")
TOKENS = Counter("rahbar_tokens_total", "LLM tokens", ["direction"])

_generation: ContextVar[dict[str, object] | None] = ContextVar("generation", default=None)
_lookups = {"hit": 0, "miss": 0}


def record_generation(model: str, tokens_in: int, tokens_out: int) -> None:
    TOKENS.labels(direction="in").inc(tokens_in)
    TOKENS.labels(direction="out").inc(tokens_out)
    _generation.set({"model": model, "tokens_in": tokens_in, "tokens_out": tokens_out})


def take_generation() -> dict[str, object]:
    """What the last generation in this request reported, for the log line."""
    info = _generation.get() or {}
    _generation.set(None)
    return info


def record_cache_lookup(hit: bool) -> None:
    result = "hit" if hit else "miss"
    CACHE_LOOKUPS.labels(result=result).inc()
    _lookups[result] += 1
    CACHE_HIT_RATIO.set(_lookups["hit"] / (_lookups["hit"] + _lookups["miss"]))
