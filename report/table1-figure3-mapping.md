## 1. Figure 3 stages → our pipeline

| Stage | What our pipeline does | File(s) | What is missing |
|---|---|---|---|
| Ingest | Copies new files into `lake/incoming/` on the `data` PVC. Extraction (PDF/HTML/MD, OCR for scans) is cached by sha256 | `indexer/pipeline/ingest.py`, `lake.py`, `extract.py`; Job `k8s/base/indexer-job.yaml` | No push trigger: ingestion runs weekly (CronJob) or on demand, not on file arrival |
| Verify | Checks quality, completeness, recency and uniqueness (sha256 plus embedding near-duplicate ≥ 0.95). A failure → `quarantine/` with a reason; a report file per run | `indexer/pipeline/verify.py`; `eval/results/verification-*.{json,txt}` | Verification has no prompt-injection scan (caught later by the retrieval rail, §4a) |
| Update data lake | `manifest.json` per doc_id/version/sha256/status. Superseded versions → `archive/`, `superseded=true` | `indexer/pipeline/lake.py`, `restore.py` | Single-node PVC (RWO), no off-cluster backup |
| Update retrieval sources | Incremental sync: chunk id = hash(doc_id, version, idx, text). Embeds only new chunks, deletes by doc_id, 0 orphans. Only the Job writes Chroma | `indexer/pipeline/sync.py`, `store.py`; CronJob `reindex` | Re-chunking (a new chunk size) needs a new collection built in full (`scripts/build_collection.py`) |
| Offline testing | One command: module, component (+ noise) and end-to-end levels. Release gate from a ConfigMap | `eval/run_suite.py`, `eval/suite/*`, `eval/gate.py`, `config/gate.yaml`, `k8s/eval-job.yaml` | Judge agreement is checked on only 10 hand-labelled answers |
| Live testing | One trace per query (stdout + `/data/traces`), `/metrics`, monitoring summary over a window | `api/app/services/tracing.py`, `tools/trace.py`, `tools/metrics_summary.py` | No alerting; no user feedback signal |
| Check coverage | Nearest golden question per live query (cosine ≥ 0.65); uncovered queries clustered into topics; exits 1 below 80 % | `eval/coverage.py`, `eval/live_queries.jsonl` | Live queries are a curated file, not sampled from production traces |
