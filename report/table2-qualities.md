# Table 2: Qualities

Baseline numbers are from `eval/results/20261124T192554Z-baseline.json`; thresholds are from `config/gate.yaml`.

| Quality | What we measure | Our threshold | Evidence |
|---|---|---|---|
| Adaptability | Effect of a chunk-size change; chunks re-embedded after a data change | recall@5 drop ≤ 0.02, MRR and nDCG@5 drop ≤ 0.05 | c600 passes 10/10 rules (`gate-candidate-c600.md`); second run embeds 0 chunks (`a2-incremental-*.log`) |
| Monitorability | recall@5 0.96, MRR 0.87, nDCG@5 0.81, faithfulness 1.0, query coverage | faithfulness ≥ 0.90; false abstention rise ≤ 0.04; query similarity 0.65, coverage ≥ 80% | Coverage 60% before, 85% after new questions (`*-coverage-*.json`); drift report `e3-drift.md` |
| Observability | One trace per query: chunks, scores, prompt, latency per stage, guardrail actions | Abstention on must-abstain questions = 1.0 | Baseline 1.0; injected library notice dropped by the retrieval rail (`e3-drift.md`) |
| Traceability | Document version, collection, embedding model and prompt hash in each trace; citations | Citation validity = 1.0 | Baseline 1.0; `tools/trace.py` rebuilds the prompt |
| Reliability | End-to-end p95 13.5 s, retrieval p95 132 ms; 3 replicas, HPA 3 to 8, `maxUnavailable: 0` | p95 without provider retries ≤ 20 s; retrieval p95 ≤ 400 ms | `gate-candidate-*.md`, `k8s/base/api.yaml` |

Result files named without a folder are in `eval/results/`.
