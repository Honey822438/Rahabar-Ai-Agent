# Release gate: candidate-c600-topk1-bad (rahbar_c600) -> FAIL

baseline `20261124T192554Z-baseline.json` (rahbar), candidate `20261125T151625Z-candidate-c600-topk1-bad.json`, rules `gate.yaml`

| metric | baseline | candidate | rule | result |
|---|---|---|---|---|
| component.recall@5 | 0.9615 | 0.8077 | drop <= 0.02 (>= 0.9415) | **FAIL** |
| component.mrr | 0.866 | 0.8077 | drop <= 0.05 (>= 0.8160) | **FAIL** |
| component.ndcg@5 | 0.8095 | 0.8077 | drop <= 0.05 (>= 0.7595) | PASS |
| e2e.abstention_correct_unanswerable | 1.0 | 1.0 | >= 1.0 | PASS |
| e2e.citation_validity | 1.0 | 1.0 | >= 1.0 | PASS |
| e2e.faithfulness | 1.0 | 1.0 | >= 0.9 | PASS |
| e2e.false_abstention_rate | 0.04 | 0.3182 | rise <= 0.04 (<= 0.0800) | **FAIL** |
| e2e.answer_correct_expect | 0.88 | 0.7273 | drop <= 0.08 (>= 0.8000) | **FAIL** |
| e2e.latency_p95_clean_s | - | 5.15 | <= 20.0 | PASS |
| e2e.latency_p95_s | 13.511 | 12.203 | <= 20.0 | report only (within) |
| component.retrieval_p95_ms | 132.3 | 113.4 | <= 400.0 | PASS |

4 enforced rule(s) failed -> **FAIL**
