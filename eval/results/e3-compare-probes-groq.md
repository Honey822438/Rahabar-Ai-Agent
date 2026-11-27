A = e3-pre-batch-b-probes (2026-11-25T15:19:37Z, rahbar_e3)
B = e3-post-batch-b-probes-groq (2026-11-25T16:49:52Z, rahbar_e3)

| metric                          |          A |          B |     B - A |
|---------------------------------|------------|------------|-----------|
| module.chunks_timed             |    20.0000 |    20.0000 |   +0.0000 |
| module.determinism_max_abs_diff |     0.0000 |     0.0000 |   +0.0000 |
| module.deterministic            |     1.0000 |     1.0000 |   +0.0000 |
| module.dimension                |   768.0000 |   768.0000 |   +0.0000 |
| module.embed_ms_per_chunk_mean  |   205.1000 |   230.1000 |  +25.0000 |
| module.embed_ms_per_chunk_p95   |   594.1000 |   590.4000 |   -3.7000 |
| module.pairs_separable          |     0.0000 |     0.0000 |   +0.0000 |
| module.paraphrase_mean_cosine   |     0.7242 |     0.7242 |   +0.0000 |
| module.paraphrase_min           |     0.6229 |     0.6229 |   +0.0000 |
| module.similarity_gap           |     0.2744 |     0.2744 |   +0.0000 |
| module.unrelated_max            |     0.6429 |     0.6429 |   +0.0000 |
| module.unrelated_mean_cosine    |     0.4498 |     0.4498 |   +0.0000 |
| component.mrr                   |     0.0000 |     0.8333 |   +0.8333 |
| component.ndcg@5                |     0.0000 |     0.8333 |   +0.8333 |
| component.questions             |     6.0000 |     6.0000 |   +0.0000 |
| component.recall@3              |     0.0000 |     0.8333 |   +0.8333 |
| component.recall@5              |     0.0000 |     0.8333 |   +0.8333 |
| component.retrieval_p50_ms      |    81.8000 |   100.6000 |  +18.8000 |
| component.retrieval_p95_ms      |   117.6000 |   155.2000 |  +37.6000 |
| e2e.abstention_accuracy         |     0.5000 |     0.6667 |   +0.1667 |
| e2e.answer_correct_expect       |     0.0000 |     0.5000 |   +0.5000 |
| e2e.citation_validity           |     1.0000 |     1.0000 |   +0.0000 |
| e2e.cites_relevant_chunk        |     0.0000 |     1.0000 |   +1.0000 |
| e2e.clean_answers               |     3.0000 |     1.0000 |   -2.0000 |
| e2e.faithfulness                |     1.0000 |     1.0000 |   +0.0000 |
| e2e.faithfulness_score_mean     |     1.0000 |     1.0000 |   +0.0000 |
| e2e.fallbacks_after_retries     |     2.0000 |     0.0000 |   -2.0000 |
| e2e.false_abstention_rate       |     0.5000 |     0.3333 |   -0.1667 |
| e2e.gemini_failures             |            |     0.0000 |         - |
| e2e.judge_unavailable           |     0.0000 |     0.0000 |   +0.0000 |
| e2e.judged                      |     2.0000 |     4.0000 |   +2.0000 |
| e2e.latency_p50_s               |     1.7460 |     1.4810 |   -0.2650 |
| e2e.latency_p95_clean_s         |     1.7460 |     0.0760 |   -1.6700 |
| e2e.latency_p95_s               |     3.0700 |     1.8260 |   -1.2440 |
| e2e.questions                   |     6.0000 |     6.0000 |   +0.0000 |
| e2e.scored                      |     4.0000 |     6.0000 |   +2.0000 |

Per-question changes (14):
- d01: first relevant rank None -> 1
- d02: first relevant rank None -> 1
- d03: first relevant rank None -> 1
- d04: first relevant rank None -> 1
- d05: first relevant rank None -> 1
- d01: expect_found False -> True
- d01: answer wording differs
- d02: expect_found False -> True
- d02: answer wording differs
- d04: answered False -> True
- d04: expect_found False -> True
- d04: fallback True -> False
- d05: answered False -> True
- d05: fallback True -> False
