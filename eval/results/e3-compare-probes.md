A = e3-pre-batch-b-probes (2026-11-25T15:19:37Z, rahbar_e3)
B = e3-post-batch-b-probes (2026-11-25T16:20:07Z, rahbar_e3)

| metric                          |          A |          B |     B - A |
|---------------------------------|------------|------------|-----------|
| module.chunks_timed             |    20.0000 |    20.0000 |   +0.0000 |
| module.determinism_max_abs_diff |     0.0000 |     0.0000 |   +0.0000 |
| module.deterministic            |     1.0000 |     1.0000 |   +0.0000 |
| module.dimension                |   768.0000 |   768.0000 |   +0.0000 |
| module.embed_ms_per_chunk_mean  |   205.1000 |   201.5000 |   -3.6000 |
| module.embed_ms_per_chunk_p95   |   594.1000 |   524.3000 |  -69.8000 |
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
| component.retrieval_p50_ms      |    81.8000 |    83.4000 |   +1.6000 |
| component.retrieval_p95_ms      |   117.6000 |   122.5000 |   +4.9000 |
| e2e.abstention_accuracy         |     0.5000 |     0.0000 |   -0.5000 |
| e2e.answer_correct_expect       |     0.0000 |     0.0000 |   +0.0000 |
| e2e.citation_validity           |     1.0000 |     1.0000 |   +0.0000 |
| e2e.cites_relevant_chunk        |     0.0000 |            |         - |
| e2e.clean_answers               |     3.0000 |     1.0000 |   -2.0000 |
| e2e.faithfulness                |     1.0000 |            |         - |
| e2e.faithfulness_score_mean     |     1.0000 |            |         - |
| e2e.fallbacks_after_retries     |     2.0000 |     5.0000 |   +3.0000 |
| e2e.false_abstention_rate       |     0.5000 |     1.0000 |   +0.5000 |
| e2e.judge_unavailable           |     0.0000 |     0.0000 |   +0.0000 |
| e2e.judged                      |     2.0000 |     0.0000 |   -2.0000 |
| e2e.latency_p50_s               |     1.7460 |     0.0700 |   -1.6760 |
| e2e.latency_p95_clean_s         |     1.7460 |     0.0700 |   -1.6760 |
| e2e.latency_p95_s               |     3.0700 |     0.0700 |   -3.0000 |
| e2e.questions                   |     6.0000 |     6.0000 |   +0.0000 |
| e2e.scored                      |     4.0000 |     1.0000 |   -3.0000 |

Per-question changes (10):
- d01: first relevant rank None -> 1
- d02: first relevant rank None -> 1
- d03: first relevant rank None -> 1
- d04: first relevant rank None -> 1
- d05: first relevant rank None -> 1
- d01: answered True -> False
- d01: fallback False -> True
- d02: answered True -> False
- d02: fallback False -> True
- d06: fallback False -> True
