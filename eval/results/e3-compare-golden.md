A = e3-pre-batch-b (2026-11-25T14:30:23Z, rahbar_e3)
B = e3-post-batch-b (2026-11-25T15:27:09Z, rahbar_e3)

| metric                              |          A |          B |     B - A |
|-------------------------------------|------------|------------|-----------|
| module.chunks_timed                 |    20.0000 |    20.0000 |   +0.0000 |
| module.determinism_max_abs_diff     |     0.0000 |     0.0000 |   +0.0000 |
| module.deterministic                |     1.0000 |     1.0000 |   +0.0000 |
| module.dimension                    |   768.0000 |   768.0000 |   +0.0000 |
| module.embed_ms_per_chunk_mean      |   212.8000 |   229.8000 |  +17.0000 |
| module.embed_ms_per_chunk_p95       |   537.9000 |   598.6000 |  +60.7000 |
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
| component.retrieval_p50_ms          |    84.1000 |    95.4000 |  +11.3000 |
| component.retrieval_p95_ms          |   120.5000 |   124.6000 |   +4.1000 |
| noise.noise delta mrr               |     0.0000 |     0.0000 |   +0.0000 |
| noise.noise delta ndcg@5            |    -0.0388 |    -0.0388 |   +0.0000 |
| noise.noise delta recall@3          |     0.0000 |     0.0000 |   +0.0000 |
| noise.noise delta recall@5          |     0.0000 |     0.0000 |   +0.0000 |
| e2e.abstention_accuracy             |     0.9677 |     1.0000 |   +0.0323 |
| e2e.abstention_correct_unanswerable |     1.0000 |     1.0000 |   +0.0000 |
| e2e.answer_correct_expect           |     0.8846 |     1.0000 |   +0.1154 |
| e2e.citation_validity               |     1.0000 |     1.0000 |   +0.0000 |
| e2e.cites_relevant_chunk            |     1.0000 |     1.0000 |   +0.0000 |
| e2e.clean_answers                   |            |     8.0000 |         - |
| e2e.faithfulness                    |     1.0000 |     1.0000 |   +0.0000 |
| e2e.faithfulness_score_mean         |     1.0000 |     1.0000 |   +0.0000 |
| e2e.fallbacks_after_retries         |     0.0000 |    13.0000 |  +13.0000 |
| e2e.false_abstention_rate           |     0.0385 |     0.0000 |   -0.0385 |
| e2e.judge_unavailable               |     0.0000 |     1.0000 |   +1.0000 |
| e2e.judged                          |    25.0000 |    13.0000 |  -12.0000 |
| e2e.latency_p50_s                   |     2.0420 |     2.7510 |   +0.7090 |
| e2e.latency_p95_clean_s             |            |     8.0200 |         - |
| e2e.latency_p95_s                   |    13.5040 |     8.0200 |   -5.4840 |
| e2e.questions                       |    31.0000 |    31.0000 |   +0.0000 |
| e2e.scored                          |    31.0000 |    18.0000 |  -13.0000 |

Per-question changes (43):
- h01: answered True -> False
- h01: expect_found True -> False
- h01: fallback False -> True
- h02: answered True -> False
- h02: fallback False -> True
- h03: fallback False -> True
- h04: answered True -> False
- h04: expect_found True -> False
- h04: fallback False -> True
- h05: answered True -> False
- h05: expect_found True -> False
- h05: fallback False -> True
- q01: answer wording differs
- q02: expect_found False -> True
- q02: answer wording differs
- q04: answer wording differs
- q05: answered True -> False
- q05: expect_found True -> False
- q05: fallback False -> True
- q06: answer wording differs
- q07: answered True -> False
- q07: expect_found True -> False
- q07: fallback False -> True
- q08: answer wording differs
- q10: answer wording differs
- q12: answer wording differs
- q15: answer wording differs
- q17: answer wording differs
- s02: answered True -> False
- s02: expect_found True -> False
- s02: fallback False -> True
- s03: answered True -> False
- s03: fallback False -> True
- s04: answered True -> False
- s04: expect_found True -> False
- s04: fallback False -> True
- s05: answered True -> False
- s05: expect_found True -> False
- s05: fallback False -> True
- s06: answered True -> False
- s06: expect_found True -> False
- s06: fallback False -> True
- u01: fallback False -> True
