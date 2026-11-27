A = baseline (2026-11-24T19:05:09Z, rahbar)
B = baseline-repeat (2026-11-24T19:26:10Z, rahbar)

| metric                              |          A |          B |     B - A |
|-------------------------------------|------------|------------|-----------|
| module.chunks_timed                 |    20.0000 |    20.0000 |   +0.0000 |
| module.determinism_max_abs_diff     |     0.0000 |     0.0000 |   +0.0000 |
| module.deterministic                |     1.0000 |     1.0000 |   +0.0000 |
| module.dimension                    |   768.0000 |   768.0000 |   +0.0000 |
| module.embed_ms_per_chunk_mean      |   227.2000 |   202.4000 |  -24.8000 |
| module.embed_ms_per_chunk_p95       |   586.5000 |   529.0000 |  -57.5000 |
| module.pairs_separable              |     0.0000 |     0.0000 |   +0.0000 |
| module.paraphrase_mean_cosine       |     0.7242 |     0.7242 |   +0.0000 |
| module.paraphrase_min               |     0.6229 |     0.6229 |   +0.0000 |
| module.similarity_gap               |     0.2744 |     0.2744 |   +0.0000 |
| module.unrelated_max                |     0.6429 |     0.6429 |   +0.0000 |
| module.unrelated_mean_cosine        |     0.4498 |     0.4498 |   +0.0000 |
| component.mrr                       |     0.8660 |     0.8660 |   +0.0000 |
| component.ndcg@5                    |     0.8095 |     0.8095 |   +0.0000 |
| component.questions                 |    26.0000 |    26.0000 |   +0.0000 |
| component.recall@3                  |     0.9231 |     0.9231 |   +0.0000 |
| component.recall@5                  |     0.9615 |     0.9615 |   +0.0000 |
| component.retrieval_p50_ms          |    93.2000 |    74.4000 |  -18.8000 |
| component.retrieval_p95_ms          |   132.3000 |   103.6000 |  -28.7000 |
| noise.noise delta mrr               |     0.0000 |     0.0000 |   +0.0000 |
| noise.noise delta ndcg@5            |    -0.0388 |    -0.0388 |   +0.0000 |
| noise.noise delta recall@3          |     0.0000 |     0.0000 |   +0.0000 |
| noise.noise delta recall@5          |     0.0000 |     0.0000 |   +0.0000 |
| e2e.abstention_accuracy             |     0.9667 |     0.9677 |   +0.0010 |
| e2e.abstention_correct_unanswerable |     1.0000 |     1.0000 |   +0.0000 |
| e2e.answer_correct_expect           |     0.8800 |     0.9231 |   +0.0431 |
| e2e.citation_validity               |     1.0000 |     1.0000 |   +0.0000 |
| e2e.cites_relevant_chunk            |     1.0000 |     1.0000 |   +0.0000 |
| e2e.faithfulness                    |     1.0000 |     1.0000 |   +0.0000 |
| e2e.faithfulness_score_mean         |     1.0000 |     1.0000 |   +0.0000 |
| e2e.fallbacks_after_retries         |     1.0000 |     0.0000 |   -1.0000 |
| e2e.false_abstention_rate           |     0.0400 |     0.0385 |   -0.0015 |
| e2e.judge_unavailable               |     1.0000 |     0.0000 |   -1.0000 |
| e2e.judged                          |    23.0000 |    25.0000 |   +2.0000 |
| e2e.latency_p50_s                   |     2.2810 |     1.9000 |   -0.3810 |
| e2e.latency_p95_s                   |    13.5110 |    14.1870 |   +0.6760 |
| e2e.questions                       |    31.0000 |    31.0000 |   +0.0000 |
| e2e.scored                          |    30.0000 |    31.0000 |   +1.0000 |

Per-question changes (19):
- h01: answer wording differs
- h02: answer wording differs
- h04: answer wording differs
- q01: answered False -> True
- q01: expect_found False -> True
- q01: fallback True -> False
- q02: expect_found False -> True
- q02: answer wording differs
- q03: answer wording differs
- q04: answer wording differs
- q05: answer wording differs
- q06: answer wording differs
- q08: answer wording differs
- q15: answer wording differs
- q17: answer wording differs
- s01: answer wording differs
- s02: answer wording differs
- s03: answer wording differs
- s06: answer wording differs

## Explanation (B4)

Both runs: same commit, seed 42, temperature 0, same collection and golden set.

- **Module and component levels are identical** (every similarity, recall, MRR and nDCG value differs by 0.0000). nomic-embed-text on Ollama is deterministic (max vector difference 0.0) and Chroma's HNSW index is queried read-only, so the same query returns the same ranked chunks. Only wall-clock latencies move (CPU load, Ollama warm-up).
- **End-to-end varies.** 13 answers are worded differently, although retrieval gave them identical evidence. Gemini's OpenAI-compatible endpoint rejects a `seed` (HTTP 400), and temperature 0 still is not bit-exact on a hosted model (batched GPU arithmetic, server-side model updates behind `gemini-flash-lite-latest`). The wording changes did not change a single faithfulness verdict, citation or abstention decision.
- **q01's change comes from an outage:** in run A the free tier returned 503 three times, and the canned fallback was reported as an outage (not scored). In run B it answered. q02's `expect` check passed only in B: the model wrote "six years" in one run and "6 years" in the other. That is a weakness of exact-substring scoring, not of the answer.
- **What we fixed in code:** a seed for Python's RNG and for the LLM where it is accepted (Groq), temperature 0, deterministic chunk ids, and a deterministic order of questions. **What we cannot fix:** hosted-model sampling and availability. So the release gate (C2) compares against tolerance bands, not exact values, and outages are excluded from the scores.
