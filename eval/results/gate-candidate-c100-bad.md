# Release gate: candidate-c100-bad (rahbar_c100) -> FAIL

baseline `20261126T160622Z-k8s-baseline.json` (rahbar), candidate `20261125T142949Z-candidate-c100-bad.json`, rules `gate.yaml`

| metric | baseline | candidate | rule | result |
|---|---|---|---|---|
| component.recall@5 | 0.9355 | 0.9615 | drop <= 0.02 (>= 0.9155) | PASS |
| component.mrr | 0.8177 | 0.9286 | drop <= 0.05 (>= 0.7677) | PASS |
| component.ndcg@5 | 0.7789 | 0.7932 | drop <= 0.05 (>= 0.7289) | PASS |
| e2e.abstention_correct_unanswerable | 1.0 | 1.0 | >= 1.0 | PASS |
| e2e.citation_validity | 1.0 | 1.0 | >= 1.0 | PASS |
| e2e.faithfulness | 1.0 | 1.0 | >= 0.9 | PASS |
| e2e.false_abstention_rate | 0.0645 | 0.04 | rise <= 0.04 (<= 0.1045) | PASS |
| e2e.answer_correct_expect | 0.8387 | 0.92 | drop <= 0.08 (>= 0.7587) | PASS |
| e2e.latency_p95_clean_s | 6.012 | - | metric missing | **FAIL** |
| e2e.latency_p95_s | 6.012 | 27.642 | <= 20.0 | report only (over) |
| component.retrieval_p95_ms | 187.3 | 254.4 | <= 400.0 | PASS |

1 enforced rule(s) failed -> **FAIL**
