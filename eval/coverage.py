"""E2 coverage: how much of the live traffic the golden set represents (RAGOps 4.3.2).

    python eval/coverage.py [--threshold 0.65] [--min-coverage 0.80] [--label X]

For every live query (eval/live_queries.jsonl) find the nearest golden question by cosine of
the pinned embedding model (nomic-embed-text, "search_query:" prefix, the same vectors the
retriever uses). A query is COVERED when that nearest cosine >= --threshold.

Threshold (0.65): from our own pairs (eval/pairs, module level of the suite) paraphrases of the
same question score 0.62-0.84 (mean 0.72) and unrelated questions 0.30-0.64 (mean 0.45).
0.65 sits just above the highest unrelated pair, so a query never counts as covered by a
golden question about something else; the cost is that a loosely worded paraphrase (< 0.65)
counts as uncovered, which errs on the side of adding golden questions.

Uncovered queries are grouped into topics (single-link clusters at cosine >= 0.60 (0.50 chained all 16 into one blob,
0.65 left only singletons), labelled
by their most common content words). Writes eval/results/<ts>-coverage-<label>.json and
exits 1 when coverage < --min-coverage (default 0.80: at least 4 in 5 live queries must
have a golden neighbour, so a whole unseen topic, here 12/40 = 30%, cannot hide).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "eval"
STOP = set("""a an the is are was were be to of in on for and or i my me can do does what
how when who which per if from with at by it its there this that much many any get need
needed what's after before your you we our about""".split())


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def embed(texts: list[str]) -> list[list[float]]:
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    model = os.environ.get("EMBED_MODEL", "nomic-embed-text")
    prefix = "search_query: " if model.startswith("nomic") else ""
    response = httpx.post(f"{url}/api/embed", timeout=120,
                          json={"model": model, "input": [prefix + t for t in texts]})
    response.raise_for_status()
    return response.json()["embeddings"]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def topics(queries: list[dict], vectors: list[list[float]], link: float) -> list[dict]:
    """Single-link clustering of the uncovered queries, labelled by common words."""
    parent = list(range(len(queries)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(queries)):
        for j in range(i + 1, len(queries)):
            if cosine(vectors[i], vectors[j]) >= link:
                parent[find(i)] = find(j)
    groups: dict[int, list[int]] = {}
    for i in range(len(queries)):
        groups.setdefault(find(i), []).append(i)
    out = []
    for members in sorted(groups.values(), key=len, reverse=True):
        words = Counter(w for i in members for w in re.findall(r"[a-z]+", queries[i]["query"].lower())
                        if w not in STOP and len(w) > 2)
        out.append({"topic": " / ".join(w for w, _ in words.most_common(3)),
                    "size": len(members), "queries": [queries[i]["id"] for i in members]})
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Golden-set coverage of live queries")
    p.add_argument("--live", type=Path, default=EVAL / "live_queries.jsonl")
    p.add_argument("--golden", type=Path, default=EVAL / "golden.jsonl")
    p.add_argument("--threshold", type=float, default=0.65)
    p.add_argument("--min-coverage", type=float, default=0.80)
    p.add_argument("--topic-link", type=float, default=0.60)
    p.add_argument("--label", default="run")
    p.add_argument("--out-dir", type=Path, default=EVAL / "results")
    args = p.parse_args()

    live, golden = read_jsonl(args.live), read_jsonl(args.golden)
    lv = embed([q["query"] for q in live])
    gv = embed([g["question"] for g in golden])
    rows = []
    for q, v in zip(live, lv):
        scores = [cosine(v, g) for g in gv]
        best = max(range(len(golden)), key=scores.__getitem__)
        rows.append({"id": q["id"], "query": q["query"], "topic_given": q.get("topic"),
                     "nearest_golden": golden[best]["id"],
                     "nearest_question": golden[best]["question"],
                     "cosine": round(scores[best], 4), "covered": scores[best] >= args.threshold})
    covered = sum(r["covered"] for r in rows)
    coverage = covered / len(rows)
    uncovered = [i for i, r in enumerate(rows) if not r["covered"]]
    groups = topics([live[i] for i in uncovered], [lv[i] for i in uncovered], args.topic_link)
    by_topic: dict[str, list[bool]] = {}
    for r in rows:
        by_topic.setdefault(r["topic_given"] or "-", []).append(r["covered"])

    result = {"label": args.label, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "golden_questions": len(golden), "live_queries": len(rows),
              "threshold": args.threshold, "min_coverage": args.min_coverage,
              "covered": covered, "coverage": round(coverage, 4),
              "coverage_by_given_topic": {t: round(sum(v) / len(v), 4) for t, v in by_topic.items()},
              "uncovered_topics": groups, "per_query": rows,
              "pass": coverage >= args.min_coverage}
    print(f"{'id':<5} {'cos':>6}  {'cov':<3}  query  ->  nearest golden")
    for r in rows:
        print(f"{r['id']:<5} {r['cosine']:>6.3f}  {'yes' if r['covered'] else 'NO':<3}  "
              f"{r['query'][:42]:<42} -> {r['nearest_golden']}")
    print(f"\ncoverage {covered}/{len(rows)} = {coverage:.1%} at cosine >= {args.threshold} "
          f"(golden: {len(golden)} questions)")
    for t, v in result["coverage_by_given_topic"].items():
        print(f"  topic {t:<22} {v:.0%}")
    print("uncovered, grouped:")
    for g in groups:
        print(f"  [{g['size']:>2}] {g['topic']:<35} {', '.join(g['queries'])}")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-coverage-{args.label}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    verdict = "PASS" if result["pass"] else "FAIL"
    print(f"\n{verdict}: coverage {coverage:.1%} vs minimum {args.min_coverage:.0%}  ->  "
          f"{out}")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
