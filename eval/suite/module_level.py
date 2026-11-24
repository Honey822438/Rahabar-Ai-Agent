"""B1 module level (the embedding model), RAGOps Table 1.

  - mean cosine of 15 paraphrase pairs vs 15 unrelated pairs, and the gap between them
  - embedding time per chunk (a sample of indexed chunks, batch of 1, wall clock)
  - determinism: embed the same texts twice, largest absolute difference in any dimension
"""

from __future__ import annotations

import statistics
import time
from typing import Any

import httpx

from .common import EVAL, read_jsonl

QUERY = "search_query: "
DOCUMENT = "search_document: "


def embed(settings: Any, texts: list[str], prefix: str) -> list[list[float]]:
    response = httpx.post(f"{settings.ollama_url}/api/embed", timeout=300,
                          json={"model": settings.embed_model, "input": [prefix + t for t in texts]})
    response.raise_for_status()
    return list(response.json()["embeddings"])


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def pair_scores(settings: Any, name: str) -> list[float]:
    pairs = read_jsonl(EVAL / "pairs" / f"{name}.jsonl")
    a = embed(settings, [p["a"] for p in pairs], QUERY)
    b = embed(settings, [p["b"] for p in pairs], QUERY)
    return [cosine(x, y) for x, y in zip(a, b)]


def sample_chunks(settings: Any, n: int) -> list[str]:
    from app.retrieval.chroma import ChromaRetriever
    collection = ChromaRetriever(settings)._collection()
    got = collection.get(limit=n, include=["documents"])
    return list(got["documents"])


def run(settings: Any, sample: int = 20) -> dict[str, Any]:
    para, unrel = pair_scores(settings, "paraphrase"), pair_scores(settings, "unrelated")
    chunks = sample_chunks(settings, sample)
    timings = []
    for text in chunks:
        started = time.perf_counter()
        embed(settings, [text], DOCUMENT)
        timings.append(time.perf_counter() - started)
    first = embed(settings, chunks, DOCUMENT)
    second = embed(settings, chunks, DOCUMENT)
    max_diff = max(abs(x - y) for v1, v2 in zip(first, second) for x, y in zip(v1, v2))
    return {
        "embed_model": settings.embed_model,
        "dimension": len(first[0]) if first else 0,
        "paraphrase_mean_cosine": round(statistics.mean(para), 4),
        "unrelated_mean_cosine": round(statistics.mean(unrel), 4),
        "similarity_gap": round(statistics.mean(para) - statistics.mean(unrel), 4),
        "paraphrase_min": round(min(para), 4), "unrelated_max": round(max(unrel), 4),
        "pairs_separable": min(para) > max(unrel),
        "embed_ms_per_chunk_mean": round(1000 * statistics.mean(timings), 1),
        "embed_ms_per_chunk_p95": round(1000 * sorted(timings)[int(0.95 * (len(timings) - 1))], 1),
        "chunks_timed": len(timings),
        "determinism_max_abs_diff": max_diff,
        "deterministic": max_diff == 0.0,
    }
