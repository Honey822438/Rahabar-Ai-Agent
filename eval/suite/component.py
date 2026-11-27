"""B2 component level (retrieval), RAGOps Table 1.

Over every golden question that has relevant chunks (answerable + hard):
  recall@3, recall@5  share of questions with at least one relevant chunk in the top K
                      (a hit rate: golden items list alternative sources, any one counts)
  MRR                 mean of 1 / rank of the first relevant chunk in the top 10 (0 if none)
  nDCG@5              binary relevance, log2 discount, ideal = all relevant first
  latency             retrieval p50 / p95 (embed + search)

Noise test: copy the collection into <collection>_noise, add the chunks of the irrelevant
documents in eval/noise/ (fictional rules of other universities + one off-topic newsletter),
re-run, and report the change in every metric.
"""

from __future__ import annotations

import math
import statistics
import time
from typing import Any

from .common import EVAL, is_relevant, percentile

DEPTH = 10


def retriever_for(settings: Any) -> Any:
    from app.retrieval.chroma import ChromaRetriever
    return ChromaRetriever(settings)


def score_question(retriever: Any, question: dict[str, Any], served: int = DEPTH
                   ) -> dict[str, Any]:
    started = time.perf_counter()
    passages = retriever.retrieve(question["question"], k=DEPTH)
    seconds = time.perf_counter() - started
    # A chunk ranked below the service's top_k never reaches the model: a miss. Applied only
    # when top_k < 5, so @3/@5 and MRR of every top_k >= 5 run keep their earlier definition.
    flags = [is_relevant(p, question["relevant"]) and (served >= 5 or i < served)
             for i, p in enumerate(passages)]
    first = next((i + 1 for i, hit in enumerate(flags) if hit), None)
    dcg = sum(1 / math.log2(i + 2) for i, hit in enumerate(flags[:5]) if hit)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(5, sum(flags) or 1)))
    return {"id": question["id"], "type": question["type"], "first_relevant_rank": first,
            "hit@3": any(flags[:3]), "hit@5": any(flags[:5]), "rr": 1 / first if first else 0.0,
            "ndcg@5": dcg / ideal if ideal else 0.0, "seconds": seconds,
            "top5": [{"chunk_id": p.chunk_id, "source": p.source, "section": p.section,
                      "page": p.page, "score": round(p.score, 4), "relevant": f}
                     for p, f in zip(passages[:5], flags[:5])]}


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    times = [r["seconds"] for r in rows]
    return {
        "questions": len(rows),
        "recall@3": round(statistics.mean(r["hit@3"] for r in rows), 4),
        "recall@5": round(statistics.mean(r["hit@5"] for r in rows), 4),
        "mrr": round(statistics.mean(r["rr"] for r in rows), 4),
        "ndcg@5": round(statistics.mean(r["ndcg@5"] for r in rows), 4),
        "retrieval_p50_ms": round(1000 * percentile(times, 50), 1),
        "retrieval_p95_ms": round(1000 * percentile(times, 95), 1),
    }


def evaluate(settings: Any, golden: list[dict[str, Any]]) -> dict[str, Any]:
    retriever = retriever_for(settings)
    rows = [score_question(retriever, q, settings.top_k) for q in golden if q["relevant"]]
    return {"collection": settings.collection, "served_top_k": settings.top_k, "summary": summarise(rows), "per_question": rows}


def build_noise_collection(settings: Any) -> tuple[str, int]:
    """<collection>_noise = every chunk of the collection + the noise documents' chunks."""
    from app.retrieval.chroma import ChromaRetriever

    from .module_level import DOCUMENT, embed
    retriever = ChromaRetriever(settings)
    source = retriever._collection()
    client = retriever._client
    name = f"{settings.collection}_noise"
    try:
        client.delete_collection(name)
    except Exception:
        pass
    target = client.create_collection(name=name, metadata={
        **{k: v for k, v in (source.metadata or {}).items() if not k.startswith("hnsw:")},
        "hnsw:space": "cosine"})
    got = source.get(include=["documents", "metadatas", "embeddings"])
    for start in range(0, len(got["ids"]), 500):
        end = start + 500
        target.add(ids=got["ids"][start:end], documents=got["documents"][start:end],
                   metadatas=got["metadatas"][start:end],
                   embeddings=[list(map(float, e)) for e in got["embeddings"][start:end]])
    noise_ids, texts, metas = [], [], []
    for path in sorted((EVAL / "noise").glob("*.md")):
        paragraphs = [p.strip() for p in path.read_text(encoding="utf-8").split("\n\n") if p.strip()]
        title = paragraphs[0].lstrip("# ")
        for i, paragraph in enumerate(paragraphs[1:]):
            noise_ids.append(f"noise-{path.stem}-{i}")
            texts.append(f"{title}\n{paragraph}")
            metas.append({"source": path.name, "section": title, "page": 1, "doc_id": path.stem,
                          "doc_version": "noise", "superseded": False})
    if not texts:
        raise FileNotFoundError(f"no noise documents in {EVAL / 'noise'}")
    target.add(ids=noise_ids, documents=texts, metadatas=metas,
               embeddings=embed(settings, texts, DOCUMENT))
    return name, len(noise_ids)


def noise_test(settings: Any, golden: list[dict[str, Any]],
               clean: dict[str, Any]) -> dict[str, Any]:
    import dataclasses
    name, added = build_noise_collection(settings)
    noisy = evaluate(dataclasses.replace(settings, collection=name), golden)
    keys = ("recall@3", "recall@5", "mrr", "ndcg@5")
    noise_in_top5 = sum(any(t["source"].startswith("noise-") for t in r["top5"])
                        for r in noisy["per_question"])
    return {"noise_collection": name, "noise_chunks_added": added,
            "noise_docs": len(list((EVAL / "noise").glob("*.md"))),
            "summary": noisy["summary"],
            "delta": {k: round(noisy["summary"][k] - clean["summary"][k], 4) for k in keys},
            "questions_with_noise_in_top5": noise_in_top5}
