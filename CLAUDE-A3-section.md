## Assignment 03 — RAGOps (active from 23 Nov 2026, due Sat 28 Nov)
Work happens on branch **`a3`** of this repo. The plan is **`PLAN-A3.md`**, the paper summary is **`PAPER-NOTES.md`**, and the assignment PDF is the spec. Everything from Assignment 02 above still applies (namespace `rahbar`, no secrets in Git, the Job is the only writer, SHA tags, `needs:`).

### A3 decisions (ask before changing)
| Area | Decision |
|---|---|
| Data lake | PVC mounted at `/data`: `lake/{incoming,verified,quarantine,archive}`, `lake/manifest.json`, `traces/traces.jsonl`, `results/`. |
| Verification | Runs after extraction, before chunking. Checks: quality, completeness, recency, uniqueness (sha256 + embedding near-dup). Fail → quarantine with a reason. A report file per run. |
| Incremental index | Chunk id = hash(doc_id, version, chunk index, text). Compare with the manifest → embed only new or changed chunks, delete removed ones by doc_id, archive superseded versions (`superseded=true`), restore script for rollback. |
| Golden set | `eval/golden.jsonl` (convert from `eval/golden.yaml`, keep Malaika's questions). Fields: id, question, type (answerable / unanswerable / hard), source (human / synthetic), reviewed, relevant [{doc_id, page, section}], expect. |
| Eval suite | One command → `eval/results/<timestamp>.json` + a summary table. Module (paraphrase vs unrelated cosine, embed time, determinism), component (recall@3/5, MRR, nDCG@5, noise test), end-to-end (faithfulness with a Gemini judge, abstention, citation validity, p50/p95). Fixed seeds. |
| Change experiment | Candidate = a different chunk size in its **own collection** (e.g. `rahbar_c600`). A deliberately bad candidate (e.g. 100/0) must fail the gate. |
| Release gate | Thresholds in `config/gate.yaml`, mounted from a **ConfigMap** in the cluster. The script exits non-zero on fail. |
| Traces | One JSON line per query to stdout **and** `/data/traces/traces.jsonl`, with every field in D1 (including the full prompt or prompt hash + stored prompt, the collection and embedding model/version, guardrail actions). `tools/trace.py <id>` rebuilds the prompt. |
| Coverage | `eval/live_queries.jsonl` (≥ 40). Nearest golden question by embedding cosine; a justified threshold; the script exits non-zero below the coverage threshold. |
| Kubernetes | Ingest Job + CronJob (the only writer), eval Job (`k8s/eval-job.yaml`, fails on gate fail), gate ConfigMap, candidate Deployment + Service + collection, rolling update `maxUnavailable: 0`, `rollout undo`. Requests and limits from `kubectl top`. |

### Team & ownership for A3
| Owner | Tasks |
|---|---|
| **Rehan (i24-3012)** | All code, scripts, manifests, runs, results, report results + short answers |
| **Malaika (i24-3098)** | **Writing and data only:** Batch B text docs, ≥ 8 human golden questions + reviewing ≥ 8 synthetic, the 30 embedding test pairs, ≥ 8 hand faithfulness labels, the 40 live queries, ≥ 6 new golden questions (E4), the D5 root-cause draft, report tables 1, 2, 5, screenshot collection |

If you are **Malaika's Claude Code**: work only on her tasks above; edit only `eval/golden.jsonl`, `eval/live_queries.jsonl`, `eval/pairs/*`, `eval/labels/*`, `data/batch_b/*.md|txt`, `report/*`. Never touch code, `k8s/` or workflows. Never push to `main`. No Co-Authored-By trailers.
