A = baseline (2026-11-24T19:05:09Z, rahbar)
B = candidate-c100-bad (2026-11-25T13:53:11Z, rahbar_c100)

| metric                              |          A |          B |     B - A |
|-------------------------------------|------------|------------|-----------|
| module.chunks_timed                 |    20.0000 |    20.0000 |   +0.0000 |
| module.determinism_max_abs_diff     |     0.0000 |     0.0000 |   +0.0000 |
| module.deterministic                |     1.0000 |     1.0000 |   +0.0000 |
| module.dimension                    |   768.0000 |   768.0000 |   +0.0000 |
| module.embed_ms_per_chunk_mean      |   227.2000 |   617.8000 | +390.6000 |
| module.embed_ms_per_chunk_p95       |   586.5000 |  1170.2000 | +583.7000 |
| module.pairs_separable              |     0.0000 |     0.0000 |   +0.0000 |
| module.paraphrase_mean_cosine       |     0.7242 |     0.7242 |   +0.0000 |
| module.paraphrase_min               |     0.6229 |     0.6229 |   +0.0000 |
| module.similarity_gap               |     0.2744 |     0.2744 |   +0.0000 |
| module.unrelated_max                |     0.6429 |     0.6429 |   +0.0000 |
| module.unrelated_mean_cosine        |     0.4498 |     0.4498 |   +0.0000 |
| component.mrr                       |     0.8660 |     0.9286 |   +0.0626 |
| component.ndcg@5                    |     0.8095 |     0.7932 |   -0.0163 |
| component.questions                 |    26.0000 |    26.0000 |   +0.0000 |
| component.recall@3                  |     0.9231 |     0.9615 |   +0.0384 |
| component.recall@5                  |     0.9615 |     0.9615 |   +0.0000 |
| component.retrieval_p50_ms          |    93.2000 |   179.3000 |  +86.1000 |
| component.retrieval_p95_ms          |   132.3000 |   254.4000 | +122.1000 |
| noise.noise delta mrr               |     0.0000 |     0.0000 |   +0.0000 |
| noise.noise delta ndcg@5            |    -0.0388 |    -0.0213 |   +0.0175 |
| noise.noise delta recall@3          |     0.0000 |     0.0000 |   +0.0000 |
| noise.noise delta recall@5          |     0.0000 |     0.0000 |   +0.0000 |
| e2e.abstention_accuracy             |     0.9667 |     0.9655 |   -0.0012 |
| e2e.abstention_correct_unanswerable |     1.0000 |     1.0000 |   +0.0000 |
| e2e.answer_correct_expect           |     0.8800 |     0.9200 |   +0.0400 |
| e2e.citation_validity               |     1.0000 |     1.0000 |   +0.0000 |
| e2e.cites_relevant_chunk            |     1.0000 |     1.0000 |   +0.0000 |
| e2e.faithfulness                    |     1.0000 |     1.0000 |   +0.0000 |
| e2e.faithfulness_score_mean         |     1.0000 |     1.0000 |   +0.0000 |
| e2e.fallbacks_after_retries         |     1.0000 |     2.0000 |   +1.0000 |
| e2e.false_abstention_rate           |     0.0400 |     0.0400 |   +0.0000 |
| e2e.judge_unavailable               |     1.0000 |     0.0000 |   -1.0000 |
| e2e.judged                          |    23.0000 |    24.0000 |   +1.0000 |
| e2e.latency_p50_s                   |     2.2810 |     1.8780 |   -0.4030 |
| e2e.latency_p95_s                   |    13.5110 |    27.6420 |  +14.1310 |
| e2e.questions                       |    31.0000 |    31.0000 |   +0.0000 |
| e2e.scored                          |    30.0000 |    29.0000 |   -1.0000 |

Per-question changes (32):
- h01: first relevant rank 3 -> 7
- h03: first relevant rank 10 -> 1
- q05: first relevant rank 3 -> 1
- q12: first relevant rank 1 -> 2
- s06: first relevant rank 4 -> 1
- h01: answered True -> False
- h01: expect_found True -> False
- h02: answer wording differs
- h03: answered False -> True
- h03: expect_found False -> True
- h04: answer wording differs
- h05: answer wording differs
- q01: answered False -> True
- q01: expect_found False -> True
- q01: fallback True -> False
- q02: expect_found False -> True
- q02: answer wording differs
- q03: answer wording differs
- q04: answer wording differs
- q05: answer wording differs
- q06: answer wording differs
- q07: answer wording differs
- q08: answer wording differs
- q12: answer wording differs
- q13: fallback False -> True
- q15: answered True -> False
- q15: expect_found True -> False
- q15: fallback False -> True
- q17: answer wording differs
- s01: answer wording differs
- s03: answer wording differs
- s04: answer wording differs
