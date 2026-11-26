# Table 1: RAGOps Figure 3 mapping

| Stage | What our pipeline does | Files | What is missing |
|---|---|---|---|
| Ingest | Reads the corpus and Batch B into a data lake, extracts text (with OCR, cached by file hash) | `indexer/pipeline/ingest.py`, `extract.py`, `lake.py` | File sources only: no API or web-crawler ingestion |
| Verify | Quality, completeness, recency and uniqueness checks (hash and embedding near-duplicate). Failures are quarantined with a reason; superseded versions are archived; each run writes a report | `indexer/pipeline/verify.py`, `eval/results/verification-*` | No consistency (contradiction) check |
| Update data lake | Keeps verified, quarantined and archived documents with a manifest of versions, hashes and chunk ids; old versions can be restored | `indexer/pipeline/lake.py`, `restore.py` | Single volume, no off-cluster backup |
| Update retrieval sources | Embeds only new or changed chunks, removes deleted ones, marks old versions `superseded=true` | `indexer/pipeline/sync.py` | Updates run on a schedule or by hand, not on a data change event |
| Offline testing | One command runs module, retrieval (with noise test) and answer-level tests, then a release gate | `eval/run_suite.py`, `eval/suite/`, `eval/gate.py`, `config/gate.yaml` | Small golden set; many questions are synthetic and not yet reviewed |
| Live testing | Candidate collection and second Deployment, gate before promotion, rolling update and rollback | `k8s/a3/candidate.yaml`, `k8s/eval-job.yaml`, `scripts/demo/f3_rollout_undo.sh` | No shadow or A/B testing on real traffic |
| Check coverage | Compares 40 live queries with the golden questions by embedding cosine; exits non-zero below the threshold | `eval/coverage.py`, `eval/live_queries.jsonl` | Live queries are synthetic, not collected from real users |
