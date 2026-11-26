---
title: "RAHBAR RAGOps — Assignment 03 Report"
subtitle: "Operating and managing a grounded RAG pipeline on Kubernetes"
author:
  - "Rehan Ahmed (i24-3012)"
  - "Malaika (i24-3098)"
date: "28 November 2026"
geometry: margin=1.8cm
fontsize: 10pt
---

**Group:** Rehan Ahmed (i24-3012) · Malaika (i24-3098)
**Repository:** branch `a3` (→ `dev` → `main`). Each Part's command: `README.md` §"Assignment 03". Cluster runbook: `k8s/README.md`.
Every number below is taken from a committed file and cites that file (`eval/results/…`, `docs/evidence/…`, `traces/…`).

## 1. Figure 3 stages → our pipeline

| Stage | What our pipeline does | File(s) | What is missing |
|---|---|---|---|
| Ingest | Copies new files into `lake/incoming/` on the `data` PVC. Extraction (PDF/HTML/MD, OCR for scans) is cached by sha256 | `indexer/pipeline/ingest.py`, `lake.py`, `extract.py`; Job `k8s/base/indexer-job.yaml` | No push trigger: ingestion runs weekly (CronJob) or on demand, not on file arrival |
| Verify | Checks quality, completeness, recency and uniqueness (sha256 plus embedding near-duplicate ≥ 0.95). A failure → `quarantine/` with a reason; a report file per run | `indexer/pipeline/verify.py`; `eval/results/verification-*.{json,txt}` | Verification has no prompt-injection scan (caught later by the retrieval rail, §4a) |
| Update data lake | `manifest.json` per doc_id/version/sha256/status. Superseded versions → `archive/`, `superseded=true` | `indexer/pipeline/lake.py`, `restore.py` | Single-node PVC (RWO), no off-cluster backup |
| Update retrieval sources | Incremental sync: chunk id = hash(doc_id, version, idx, text). Embeds only new chunks, deletes by doc_id, 0 orphans. Only the Job writes Chroma | `indexer/pipeline/sync.py`, `store.py`; CronJob `reindex` | Re-chunking (a new chunk size) needs a new collection built in full (`scripts/build_collection.py`) |
| Offline testing | One command: module, component (+ noise) and end-to-end levels. Release gate from a ConfigMap | `eval/run_suite.py`, `eval/suite/*`, `eval/gate.py`, `config/gate.yaml`, `k8s/eval-job.yaml` | The hand faithfulness labels for judge agreement are still being filled in |
| Live testing | One trace per query (stdout + `/data/traces`), `/metrics`, monitoring summary over a window | `api/app/services/trace.py`, `tools/trace.py`, `tools/metrics_summary.py` | No alerting; no user feedback signal |
| Check coverage | Nearest golden question per live query (cosine ≥ 0.65); uncovered queries clustered into topics; exits 1 below 80 % | `eval/coverage.py`, `eval/live_queries.jsonl` | Live queries are a curated file, not sampled from production traces |

## 2. Table 2 qualities

| Quality | What we measure | Threshold | Evidence |
|---|---|---|---|
| Adaptability | A change (chunk size) goes through its own collection + gate, and the live api is switched with a rolling update | gate rules in `config/gate.yaml` (recall@5 drop ≤ 0.02, MRR/nDCG drop ≤ 0.05, …) | c600 PASS: `eval/results/gate-k8s-c600.md`, `docs/evidence/a3-eval-k8s-c600.txt` |
| Monitorability | top-1 similarity distribution, abstention, cache hits, fallbacks, per-stage p50/p95, injection flags | latency p95 (clean) ≤ 20 s; retrieval p95 ≤ 400 ms | `docs/evidence/a3-d3-metrics-summary.txt`, `docs/evidence/a3-f4-metrics.txt` |
| Observability | Every request: trace with chunk ids, scores, filters, prompt hash, model params, guardrail actions, latency per stage | 100 % of queries traced | `traces/traces.jsonl` (365 records), `tools/trace.py` |
| Traceability | The prompt rebuilt from the trace matches the stored sha256. Collection + embedding model/version recorded | hash match = exit 0 | `docs/evidence/a3-demo-check.txt` (trace tool PASS); `docs/evidence/a3-f3-rollout-undo.txt` |
| Reliability | Must-abstain questions abstain; citations ⊆ retrieved chunks; faithfulness; Gemini → Groq failover | abstention (unanswerable) = 1.0, citation validity = 1.0, faithfulness ≥ 0.9 | `eval/results/20261126T160622Z-k8s-baseline.json` |

## 3. Results (Parts A–F)

### A. Verification and incremental indexing
Batch B: 12 files: 6 Markdown test documents and 6 broken files (`eval/results/verification-20261125T152701Z.txt`).

| Check (first failing) | Documents caught | Examples |
|---|---|---|
| Quality | 4 | corrupt PDF (no /Root), truncated PDF (EOF), empty upload (0 chars), garbled notice (clean ratio 0.53 < 0.9) |
| Uniqueness | 3 | 2 exact sha256 mirrors; grading re-upload, a near-duplicate at cosine 0.989 ≥ 0.95 |
| Completeness | 1 | lab safety: missing source, title, doc_version |
| Verified | 4 | career fair, sports week, newer faculty policy (2026-11), library notice (contains an injected instruction) |

Sync after Batch B: 10 chunks embedded, 19 flipped to `superseded`, 0 orphans (`eval/results/e3-ingest-batch-b.log`).
Incremental behaviour (`eval/results/a2-incremental-20261124T181904Z.log`):

| Run | embedded | deleted | superseded flipped | orphans |
|---|---|---|---|---|
| Unchanged corpus | 0 | 0 | 0 | 0 |
| Changed doc (grading page v2026-b) | 7 | 0 | 7 | 0 |
| Deleted doc (faculty policy) | 0 | 19 | 0 | 0 |
| Rollback (`restore.py` grading-page@2026) | 0 | 0 | 14 | 0 |

In-cluster ingest Job on an unchanged corpus: 13 live docs, 421 chunks, **0 embedded**, 0 orphans (`docs/evidence/a3-ingest-job.txt`).

### B. Evaluation suite (baseline, collection `rahbar`, 400/50 words, top_k 5, seed 42)
Golden set: 39 questions (26 answerable, 8 unanswerable, 5 hard; 17 human, 22 synthetic) in `eval/golden.jsonl`. Results: `eval/results/20261126T160622Z-k8s-baseline.json`.

| Level | Metric | Value |
|---|---|---|
| Module | paraphrase / unrelated mean cosine (gap) | 0.724 / 0.450 (0.274) |
| Module | paraphrase min / unrelated max | 0.623 / 0.643 (overlap) |
| Module | determinism (max abs diff, two embeddings) | 0.0 |
| Component (31 q.) | recall@3 / recall@5 / MRR / nDCG@5 | 0.903 / 0.936 / 0.818 / 0.779 |
| Component | noise test (Δ recall@5 / Δ nDCG@5, 13 q. with noise in the top 5) | 0.000 / −0.029 |
| Component | retrieval p50 / p95 | 134.5 / 187.3 ms |
| End-to-end (39 q.) | abstention on unanswerable / false abstention | 1.00 / 0.065 |
| End-to-end | citation validity / faithfulness (judge, 29 judged) | 1.00 / 1.00 |
| End-to-end | answer contains expected fact | 0.839 |
| End-to-end | latency p50 / p95 | 4.34 / 6.01 s |

Stochasticity (B4), two seeded runs (`eval/results/b4-stochasticity.md`): every retrieval and module metric is identical (Δ = 0). Only the timings move (retrieval p95 −28.7 ms). At temperature 0 the answers differ only in wording.

### C. One change + release gate
Candidate: chunk size 600/100 in its own collection `rahbar_c600` (382 chunks), gated against the baseline above.

| Run | recall@5 | MRR | nDCG@5 | false abst. | correct | faithful | clean p95 s | retr. p95 ms | Gate |
|---|---|---|---|---|---|---|---|---|---|
| baseline 400/50 | 0.936 | 0.818 | 0.779 | 0.065 | 0.839 | 1.00 | 6.01 | 187 | — |
| c600 600/100 | 0.936 | 0.824 | 0.753 | 0.065 | 0.871 | 1.00 | 5.76 | 184 | **PASS** (0 rules failed) |
| c600 + top_k=1 (deliberately bad) | 0.742 | 0.742 | 0.742 | 0.290 | 0.710 | 1.00 | 5.59 | 459 | **FAIL** (5 rules: recall@5, MRR, false abst., correct, retr. p95) |

Files: `eval/results/20261126T161842Z-k8s-c600.json`, `docs/evidence/a3-eval-k8s-c600.txt`, `eval/results/20261126T192021Z-k8s-c600-topk1-bad.json`, `docs/evidence/a3-eval-k8s-c600-topk1-bad.txt`.
Earlier evidence that the gate was too noisy: the 100/0 candidate failed only on all-calls p95 (27.6 s), after Gemini 429 retries on 12/31 questions. Its quality did not get worse (`eval/results/c1-c2-summary.md`). So we now enforce p95 over answers that needed no provider retry, and only report the all-calls p95.

**Release decision: RELEASE c600.** Every enforced rule passes. recall@5 is unchanged, MRR +0.007, correct answers +0.032, and abstention, citations and faithfulness stay at 1.0. nDCG@5 −0.026 is within the 0.05 tolerance, and both p95 values fall. The top_k=1 candidate is **rejected**: a relevant chunk at rank 2+ never reaches the model, so false abstentions rise and recall drops.

### D. Traces and monitoring
- One JSON line per query to stdout and `/data/traces/traces.jsonl`. The committed copy is `traces/traces.jsonl` (365 requests, 25 Nov).
- `python -m tools.trace <id>` rebuilds the prompt and checks its sha256 (`docs/evidence/a3-demo-check.txt`: "prompt rebuilt, hash matches").
- Monitoring summary over the window (`docs/evidence/a3-d3-metrics-summary.txt`):
  - top-1 similarity: p10 0.681, p50 0.780, p90 0.869
  - abstention rate 15.1 %
  - fallback rate 41.1 % (Gemini free-tier outages during suite runs)
  - p95 retrieve 41 ms, generate 13 982 ms
  - injection flagged on 17 requests: 14 query rail, 3 retrieval rail
- Guardrail (D4): the Batch B library notice is dropped by `retrieval_injection` in 3 traces, e.g. `63539cb2…` (`eval/results/e3-drift.md`), and its injected "1.00" never reaches the prompt.

**D5 root cause from one trace (Malaika).** TODO-D5: Malaika writes 5 lines from trace `2f213c99a8ea41e597f4a678946f98e3` (`python -m tools.trace 2f213c99a8ea41e597f4a678946f98e3 --file traces/traces.jsonl`). The trace is an attendance question wrongly abstained on the 100/0 collection.

### E. Coverage and drift

| | golden q. | live q. | covered (cos ≥ 0.65) | coverage | exit |
|---|---|---|---|---|---|
| Before E4 | 31 | 40 | 24 | 0.60 | 1 (FAIL) |
| After E4 (+8 questions) | 39 | 40 | 34 | 0.85 | 0 (PASS) |

Files: `eval/results/20261125T164923Z-coverage-before-e4.json`, `…164929Z-coverage-after-e4.json`. The largest uncovered topic before E4 was "hostel / timings / girls" (4 queries).
Drift (E3), Batch B ingested, same generator (Groq) on both sides, golden 31: recall@5 / MRR 0.962 / 0.866 before and after; expected fact 0.769 → 0.769; faithfulness 0.960 → 0.917, which is one judged answer. On the drift probes, recall@5 rises from 0.000 to 0.833 (`eval/results/e3-drift.md`). An apparent drop (0.885 → 0.769) in an earlier comparison was caused by changing the LLM (Gemini → Groq), not by the data.

### F. Kubernetes

| Item | Result | Evidence |
|---|---|---|
| Eval Job, as committed | Complete, gate **PASS** | `docs/evidence/a3-eval-job-default.txt` |
| Gate ConfigMap edit (faithfulness min 0.9 → 1.01), same image | PASS → **FAIL** (Job Failed), then restored | `docs/evidence/a3-f2-configmap-gate.txt` |
| Rolling update to `rahbar_c600` + `rollout undo` | trace collection `rahbar` → `rahbar_c600` → `rahbar`, embedding `nomic-embed-text@0a109f422b47` | `docs/evidence/a3-f3-rollout-undo.txt` |
| `/metrics` via port-forward | request count, latency, cache, abstentions, tokens | `docs/evidence/a3-f4-metrics.txt` |
| `kubectl top`, 4 concurrent queries | api 105–295m CPU / 66–68 Mi (req 100m/128Mi, lim 500m/384Mi); chroma 165 Mi (lim 768 Mi); HPA cpu 30 %/70 % | `docs/evidence/a3-f5-kubectl-top.txt` |

We sized requests and limits from these measurements. Under load the api peaked at 295m, so a 500m limit leaves headroom without throttling. Memory stays at about 70 Mi, so 128 Mi is a safe request.

## 4. Short answers

**(a)** The **quality** check caught the most (4 of 8 quarantined: corrupt, truncated, empty, garbled), followed by uniqueness (3). We did **not** catch the **injected instruction** in the library notice. It is well-formed, unique and complete, so it was verified and indexed. The retrieval-time injection rail dropped it in 3 traces (§D), but at the cost of a fact that lives only in that file. An injection-pattern scan inside verification would catch it and quarantine the document before indexing.

**(b)** Module level looked fine on average: paraphrase vs unrelated mean cosine gap 0.274, deterministic embeddings. But the extremes overlap: `pairs_separable=False`, because the lowest paraphrase pair (0.6229) scores below the highest unrelated pair (0.6429) (`eval/results/20261126T160622Z-k8s-baseline.json`). No single cosine cut-off separates them, so a mean gap alone overstates the embedder. Yet the 100/0 chunking, with the same embedder, wrongly abstained on an attendance question (trace `2f213c99…`) that the 400/50 index answers (trace `36417609…`, `traces/traces.jsonl`). And top_k = 1 leaves every module metric unchanged but raises false abstention at the end-to-end level (§C). Module metrics test the embedder alone, not chunking or the top_k cut-off.

**(c)** We **archive**. A newer version flips the old chunks to `superseded=true` and moves the file to `archive/`. Retrieval filters on `superseded=false` unless the question asks about an older version. If we deleted: "what did the 2022 policy say?" could not be answered, `restore.py` rollback (14 chunks flipped back, 0 orphans) would be impossible, and old traces would cite chunk ids that no longer exist, breaking traceability.

**(d)** We trust **faithfulness (LLM judge)** least. It is one Gemini model grading its own family's output, it scored 1.00 on every run, and it moved 0.960 → 0.917 with no data change (one answer out of 24). Hand labels (TODO: Malaika, `eval/labels/faithfulness_hand.jsonl`) are still needed to measure judge agreement. The all-calls p95 latency is a close second, because it measures Gemini's free-tier minute rather than our pipeline (§C).

**(e)** **Release testing with a stochastic generator** was hardest to apply. The paper assumes the offline suite measures the candidate, but our e2e numbers moved with provider outages (41 % fallbacks in the trace window) and with the provider (Gemini vs Groq, −0.116 expected fact). We changed three things from the paper:
- the gate enforces p95 over answers with no provider retry;
- drift is compared with the same generator on both sides;
- retrieval rules carry the strict tolerances, because retrieval is deterministic.

**(f)**
- **Job `indexer` + CronJob `reindex`** are the only writers to Chroma: the api only reads, and the NetworkPolicy allows only api + indexer → chroma.
- **PVC `data`** is the data lake, quarantine, archive, traces and results.
- **StatefulSet `chroma`** (with its PVC) is the retrieval source.
- **ConfigMap `gate-config`** holds the release-gate policy.
- **Job `eval`** is offline testing, and its exit code is the gate.
- **Deployment/Service `api-candidate`** is a candidate kept separate from live traffic.
- **Deployment `api`** (`maxUnavailable: 0`, `rollout undo`) is safe promotion and rollback.
- **ConfigMap `rahbar-config`** pins the embedding model for api and indexer.
- **HPA + requests/limits** are reliability under load.

## 5. Contribution and AI statement

| Member | Contribution |
|---|---|
| Rehan Ahmed (i24-3012) | All code, scripts and Kubernetes manifests; the data lake, verification and incremental sync; the eval suite, gate and coverage; traces and tools; every run and result; Batch B; drafts of every input; report results and short answers |
| Malaika (i24-3098) | 17 human-written golden questions; TODO-MALAIKA: review of ≥ 8 synthetic questions, hand faithfulness labels, edits to pairs/live queries, D5 root cause, tables 1, 2 and 5 review, screenshot collection |

**AI statement.** We used Claude Code (Anthropic) to help write code, scripts, Kubernetes manifests and drafts of documents and test inputs. We ran every experiment on our own cluster, and we reviewed, labelled and checked the results ourselves. Every number in this report comes from a committed result file.

\newpage

## Appendix: Screenshots
Each screenshot shows the command and its output from our own cluster (`docs/evidence/<label>.png`).

TODO-SCREENSHOTS: **D1** (one full trace record), **D2** (trace tool rebuilding the prompt), **E1** (coverage before), **E2** (coverage after) are still missing. Commands: `docs/screenshot-commands.md` §D, §E.

<div class="shot"><p><b>A1: Batch B verification report (pass/fail per check, with reasons)</b></p><img src="docs/evidence/A1.png"></div>

<div class="shot"><p><b>A2: second ingestion run on an unchanged corpus, 0 chunks embedded</b></p><img src="docs/evidence/A2.png"></div>

<div class="shot"><p><b>B: evaluation summary, all three levels</b></p><img src="docs/evidence/B2.png"></div>

<div class="shot"><p><b>C1: release gate PASS (candidate c600)</b></p><img src="docs/evidence/C1.png"></div>

<div class="shot"><p><b>C2: release gate FAIL (candidate top_k = 1)</b></p><img src="docs/evidence/C2.png"></div>

<div class="shot"><p><b>F1: kubectl get all,pvc,configmap,cronjob,job -n rahbar</b></p><img src="docs/evidence/F1.png"></div>

<div class="shot"><p><b>F2a: logs of a completed ingestion Job</b></p><img src="docs/evidence/F2.png"></div>

<div class="shot"><p><b>F2b: logs of a completed evaluation Job (gate PASS)</b></p><img src="docs/evidence/F2b.png"></div>

<div class="shot"><p><b>F3/F4: gate result changing after a ConfigMap edit; rollout status + rollout undo + trace showing the previous collection and embedding version</b></p><img src="docs/evidence/F3-4.png"></div>

<div class="shot"><p><b>F5: /metrics via kubectl port-forward</b></p><img src="docs/evidence/F5.png"></div>

<div class="shot"><p><b>F6: kubectl top pods + HPA (requests/limits evidence)</b></p><img src="docs/evidence/F6.png"></div>

