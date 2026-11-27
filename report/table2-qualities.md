## 2. Table 2 qualities

| Quality | What we measure | Threshold | Evidence |
|---|---|---|---|
| Adaptability | A change (chunk size) goes through its own collection + gate, and the live api is switched with a rolling update | gate rules in `config/gate.yaml` (recall@5 drop ≤ 0.02, MRR/nDCG drop ≤ 0.05, …) | c600 PASS: `eval/results/gate-k8s-c600.md`, `docs/evidence/a3-eval-k8s-c600.txt` |
| Monitorability | top-1 similarity distribution, abstention, cache hits, fallbacks, per-stage p50/p95, injection flags | latency p95 (clean) ≤ 20 s; retrieval p95 ≤ 400 ms | `docs/evidence/a3-d3-metrics-summary.txt`, `docs/evidence/a3-f4-metrics.txt` |
| Observability | Every request: trace with chunk ids, scores, filters, prompt hash, model params, guardrail actions, latency per stage | 100 % of queries traced | `traces/traces.jsonl` (365 records), `tools/trace.py` |
| Traceability | The prompt rebuilt from the trace matches the stored sha256. Collection + embedding model/version recorded | hash match = exit 0 | `docs/evidence/a3-demo-check.txt` (trace tool PASS); `docs/evidence/a3-f3-rollout-undo.txt` |
| Reliability | Must-abstain questions abstain; citations ⊆ retrieved chunks; faithfulness; Gemini → Groq failover | abstention (unanswerable) = 1.0, citation validity = 1.0, faithfulness ≥ 0.9 | `eval/results/20261126T160622Z-k8s-baseline.json` |
