"""Re-check CACHE_THRESHOLD against question pairs, using the API's embedding and cosine.

Needs host Ollama only (no cluster, no Gemini):  python eval/cache_threshold.py
"""

from __future__ import annotations

import json
import math
import os
import urllib.request

OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")
THRESHOLDS = [0.85, 0.90, 0.92, 0.93, 0.94, 0.95, 0.96]

# The same question typed again, differing at most in case, spacing or punctuation.
REPEATS = [
    ("What is the minimum CGPA to graduate?", "What is the minimum CGPA to graduate?"),
    ("What is the minimum CGPA to graduate?", "what is the minimum cgpa to graduate"),
    ("What is the attendance requirement?", "What is the attendance requirement ?"),
    ("How many times can a course be repeated?", "How many times can a course be repeated"),
    ("What does clause 1.25 say?", "what does clause 1.25 say?"),
]
# Reworded, same answer: a hit is useful, a miss only costs one model call.
PARAPHRASES = [
    ("What is the minimum CGPA to graduate?", "What minimum CGPA do I need to graduate?"),
    ("What is the attendance requirement?", "What attendance is required?"),
    ("How many times can a course be repeated?", "How many times may I repeat a course?"),
    ("What happens if I fail a course?", "What happens when a student fails a course?"),
    ("Who approves a semester freeze?", "Who approves freezing a semester?"),
    ("What is the late fee fine?", "What is the fine for paying fees late?"),
    ("What is the policy on plagiarism?", "What is the plagiarism policy?"),
    ("How is the GPA calculated?", "How do you calculate GPA?"),
]
# Different answers: any hit here serves a wrong answer.
MUST_MISS = [
    ("What minimum CGPA must an MS student maintain to avoid a warning?",
     "What minimum CGPA must an undergraduate student maintain to avoid a warning?"),
    ("What does clause 1.21 say?", "What does clause 1.25 say?"),
    ("What does clause 1.26 say?", "What does clause 1.25 say?"),
    ("What is the minimum CGPA to graduate from BS?", "What is the minimum CGPA to graduate from MS?"),
    ("What is the minimum CGPA for a PhD student?", "What is the minimum CGPA for an MS student?"),
    ("What is the tuition fee for BS?", "What is the tuition fee for MS?"),
    ("What is the attendance requirement for lectures?", "What is the attendance requirement for labs?"),
    ("Can a course be dropped?", "Can a course be repeated?"),
    ("What is the grade for 85 marks?", "What is the grade for 75 marks?"),
    ("How many credit hours can a student take in fall?",
     "How many credit hours can a student take in summer?"),
    ("Who approves a semester freeze?", "Who approves a semester withdrawal?"),
    ("What is the penalty for plagiarism?", "What is the penalty for cheating?"),
]


def embed(text: str) -> list[float]:
    body = json.dumps({"model": MODEL, "input": "search_query: " + text}).encode()
    request = urllib.request.Request(f"{OLLAMA}/api/embed", body,
                                     {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)["embeddings"][0]


def cosine(a: list[float], b: list[float]) -> float:
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b)) / norm


def score(pairs: list[tuple[str, str]]) -> list[tuple[float, str, str]]:
    return sorted(((cosine(embed(a), embed(b)), a, b) for a, b in pairs), reverse=True)


def main() -> None:
    groups = {name: score(pairs) for name, pairs in
              (("repeat", REPEATS), ("paraphrase", PARAPHRASES), ("must-miss", MUST_MISS))}
    for name, rows in groups.items():
        print(f"\n{name}")
        for value, a, b in rows:
            print(f"  {value:.3f}  {a} | {b}")
    print("\nthreshold  repeat  paraphrase  false hits")
    for t in THRESHOLDS:
        hits = {name: sum(value >= t for value, _, _ in rows) for name, rows in groups.items()}
        print(f"{t:<10} {hits['repeat']}/{len(REPEATS)}     {hits['paraphrase']}/{len(PARAPHRASES)}"
              f"         {hits['must-miss']}/{len(MUST_MISS)}")


if __name__ == "__main__":
    main()
