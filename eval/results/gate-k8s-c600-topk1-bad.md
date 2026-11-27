# Release gate: k8s-c600-topk1-bad (rahbar_c600) -> FAIL

baseline `20261126T160622Z-k8s-baseline.json` (rahbar), candidate `20261126T192021Z-k8s-c600-topk1-bad.json`, rules `gate.yaml`

| metric | baseline | candidate | rule | result |
|---|---|---|---|---|
| component.recall@5 | 0.9355 | 0.7419 | drop <= 0.02 (>= 0.9155) | **FAIL** |
| component.mrr | 0.8177 | 0.7419 | drop <= 0.05 (>= 0.7677) | **FAIL** |
| component.ndcg@5 | 0.7789 | 0.7419 | drop <= 0.05 (>= 0.7289) | PASS |
| e2e.abstention_correct_unanswerable | 1.0 | 1.0 | >= 1.0 | PASS |
| e2e.citation_validity | 1.0 | 1.0 | >= 1.0 | PASS |
| e2e.faithfulness | 1.0 | 1.0 | >= 0.9 | PASS |
| e2e.false_abstention_rate | 0.0645 | 0.2903 | rise <= 0.04 (<= 0.1045) | **FAIL** |
| e2e.answer_correct_expect | 0.8387 | 0.7097 | drop <= 0.08 (>= 0.7587) | **FAIL** |
| e2e.latency_p95_clean_s | 6.012 | 5.591 | <= 20.0 | PASS |
| e2e.latency_p95_s | 6.012 | 5.591 | <= 20.0 | report only (within) |
| component.retrieval_p95_ms | 187.3 | 458.8 | <= 400.0 | **FAIL** |

5 enforced rule(s) failed -> **FAIL**
