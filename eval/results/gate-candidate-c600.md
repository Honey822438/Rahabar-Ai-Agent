# Release gate: candidate-c600 (rahbar_c600) -> PASS

baseline `20261124T192554Z-baseline.json` (rahbar), candidate `20261125T135310Z-candidate-c600.json`, rules `gate.yaml`

| metric | baseline | candidate | rule | result |
|---|---|---|---|---|
| component.recall@5 | 0.9615 | 0.9615 | drop <= 0.02 (>= 0.9415) | PASS |
| component.mrr | 0.866 | 0.8673 | drop <= 0.05 (>= 0.8160) | PASS |
| component.ndcg@5 | 0.8095 | 0.775 | drop <= 0.05 (>= 0.7595) | PASS |
| e2e.abstention_correct_unanswerable | 1.0 | 1.0 | >= 1.0 | PASS |
| e2e.citation_validity | 1.0 | 1.0 | >= 1.0 | PASS |
| e2e.faithfulness | 1.0 | 1.0 | >= 0.9 | PASS |
| e2e.false_abstention_rate | 0.04 | 0.0417 | rise <= 0.04 (<= 0.0800) | PASS |
| e2e.answer_correct_expect | 0.88 | 0.9167 | drop <= 0.08 (>= 0.8000) | PASS |
| e2e.latency_p95_s | 13.511 | 16.596 | <= 20.0 | PASS |
| component.retrieval_p95_ms | 132.3 | 288.4 | <= 400.0 | PASS |

10/10 rules passed -> **PASS**
