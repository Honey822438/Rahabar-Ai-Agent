A = e3-pre-batch-b-groq (2026-11-25T18:16:55Z, rahbar_e3pre)
B = e3-post-batch-b-groq (2026-11-25T17:01:32Z, rahbar_e3)

| metric                              |          A |          B |     B - A |
|-------------------------------------|------------|------------|-----------|
| module.chunks_timed                 |    20.0000 |    20.0000 |   +0.0000 |
| module.determinism_max_abs_diff     |     0.0000 |     0.0000 |   +0.0000 |
| module.deterministic                |     1.0000 |     1.0000 |   +0.0000 |
| module.dimension                    |   768.0000 |   768.0000 |   +0.0000 |
| module.embed_ms_per_chunk_mean      |   283.8000 |   204.9000 |  -78.9000 |
| module.embed_ms_per_chunk_p95       |   779.4000 |   532.4000 | -247.0000 |
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
| component.retrieval_p50_ms          |   111.1000 |   102.0000 |   -9.1000 |
| component.retrieval_p95_ms          |   149.9000 |   135.0000 |  -14.9000 |
| noise.noise delta mrr               |     0.0000 |     0.0000 |   +0.0000 |
| noise.noise delta ndcg@5            |    -0.0388 |    -0.0388 |   +0.0000 |
| noise.noise delta recall@3          |     0.0000 |     0.0000 |   +0.0000 |
| noise.noise delta recall@5          |     0.0000 |     0.0000 |   +0.0000 |
| e2e.abstention_accuracy             |     0.9677 |     0.9677 |   +0.0000 |
| e2e.abstention_correct_unanswerable |     1.0000 |     1.0000 |   +0.0000 |
| e2e.answer_correct_expect           |     0.7692 |     0.7692 |   +0.0000 |
| e2e.citation_validity               |     1.0000 |     1.0000 |   +0.0000 |
| e2e.cites_relevant_chunk            |     1.0000 |     1.0000 |   +0.0000 |
| e2e.clean_answers                   |     1.0000 |     1.0000 |   +0.0000 |
| e2e.faithfulness                    |     0.9600 |     0.9167 |   -0.0433 |
| e2e.faithfulness_score_mean         |     0.9500 |     0.9653 |   +0.0153 |
| e2e.fallbacks_after_retries         |     0.0000 |     0.0000 |   +0.0000 |
| e2e.false_abstention_rate           |     0.0385 |     0.0385 |   +0.0000 |
| e2e.gemini_failures                 |    30.0000 |    30.0000 |   +0.0000 |
| e2e.judge_unavailable               |     0.0000 |     1.0000 |   +1.0000 |
| e2e.judged                          |    25.0000 |    24.0000 |   -1.0000 |
| e2e.latency_p50_s                   |     1.6080 |     1.5380 |   -0.0700 |
| e2e.latency_p95_clean_s             |     0.0750 |     0.0710 |   -0.0040 |
| e2e.latency_p95_s                   |     1.9270 |     2.1440 |   +0.2170 |
| e2e.questions                       |    31.0000 |    31.0000 |   +0.0000 |
| e2e.scored                          |    31.0000 |    31.0000 |   +0.0000 |

Per-question changes (18):
- h01: expect_found False -> True
- h01: answer wording differs
- h02: answer wording differs
- h04: answer wording differs
- h05: expect_found True -> False
- h05: answer wording differs
- q01: answer wording differs
- q02: answer wording differs
- q05: answer wording differs
- q06: answer wording differs
- q07: answer wording differs
- q08: answer wording differs
- q10: answer wording differs
- q11: answer wording differs
- q12: answer wording differs
- q15: answer wording differs
- q17: answer wording differs
- s03: answer wording differs
