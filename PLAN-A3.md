# PLAN-A3.md — Assignment 03 (RAGOps), due **Sat 28 Nov 2026**
Builds on RAHBAR (Assignment 02) in the same repo, branch **`a3`** (PRs into `dev`, then `main`). 185 marks.
**Team:** Rehan (i24-3012), the engineering. **Malaika (i24-3098)**, the writing and data tasks marked **[M]**. Both must be able to **explain every part at the demo**.
Rules: every number in the report comes from our own runs; result files are committed under `eval/results/` and `traces/`; all manifests under `k8s/`. **The demo must run on Kubernetes (Docker only = 0).**
Read `PAPER-NOTES.md` first.
**Rule: nothing of ours waits for Malaika.** Rehan/Claude Code drafts every input (labelled `source: synthetic`, `reviewed: false`) and the pipeline uses the drafts now. **[M]** now means *Malaika edits or replaces the draft*; her own deliverables are the ≥ 8 hand faithfulness labels, report tables 1, 2, 5 and the screenshots. `scripts/validate_inputs.py` (in CI) guards every edit.

Tick `[x]` only when **Done when** passes.

---
## Day 1 · Tue 24 — Data management (Part A)
- [x] **A0 Data lake layout** on a PVC: `/data/lake/{incoming,verified,quarantine,archive}` + `manifest.json` (doc_id, version, sha256, status, chunk_ids, timestamps).
- [x] **A1 Verification stage** (after extraction, before chunking): per document, pass or fail + a reason for **quality** (empty / garbled / failed extraction), **completeness** (source, title, date or version, page count; not truncated), **recency** (newer version of the same doc_id detected), **uniqueness** (exact sha256 dup; near-dup by embedding cosine ≥ a threshold). Failures → quarantine, not indexed. Write `eval/results/verification-<timestamp>.json` + a readable table.
  *Done when:* a run prints the per-doc, per-check table and quarantines the failures.
- [x] **A2 Incremental update:** deterministic chunk ids; unchanged corpus → **0 chunks embedded** (print counts); a changed doc replaces only its chunks; a deleted doc leaves **0 orphans** (count by doc_id); superseded version → `archive/` + `superseded=true` (excluded from retrieval); **restore / rollback** script.
  *Done when:* a second run shows 0 embedded; the orphan count is 0; rollback is shown.
- [x] **A3 Batch B** (Rehan drafts all; **[M]** may improve the text docs): ≥ 10 docs: 2+ exact duplicates, 1 near-duplicate, 1 truncated or corrupt, 1 missing metadata, 1 newer version of an existing doc, 1 with an injected instruction (+ fillers). Run both batches through A1 and A2.

## Day 2 · Wed 25 — Offline testing suite (Part B)
- [x] **B0 Golden set → `eval/golden.jsonl`**, **≥ 25 questions**: ≥ 15 answerable (doc + page), ≥ 5 unanswerable, ≥ 5 hard (paraphrased / multi-chunk / from Batch B). Field `source: human|synthetic`; ≥ 8 human, ≥ 8 synthetic reviewed (`reviewed: true`).
  Draft done (17 human by Malaika from A02 + 14 synthetic). **[M]** reviews ≥ 8 synthetic (`reviewed: true`) and may add human ones.
- [x] **B1 Module level:** 15 paraphrase + 15 unrelated pairs (draft in `eval/pairs/`, **[M]** edits); script: mean cosine of each group, the gap, embedding time per chunk, determinism (embed twice, max difference).
- [x] **B2 Component level:** recall@3, recall@5, **MRR, nDCG@5**; **noise test** (≥ 3 irrelevant docs added, or typos in queries) → the change in each metric.
- [x] **B3 End-to-end:** **faithfulness** (LLM judge), abstention correctness, citation validity, latency p50 / p95. **[M] hand-labels ≥ 8 answers** (`eval/labels/faithfulness.jsonl`: id, question_id, faithful) → judge agreement %.
- [x] **B4 Stochasticity:** fixed seeds, run twice, difference per metric + an explanation.
- [x] **B5 One command** runs everything → `eval/results/<timestamp>.json` + a summary table.

## Day 3 · Thu 26 — Gate, traces, drift (Parts C, D, E)
- [ ] **C1 One change:** candidate = a different **chunk size** (its own collection, e.g. `rahbar_c600`). Run the suite on the baseline and the candidate, compare all three levels.
- [ ] **C2 Release gate:** `config/gate.yaml` (recall@5 drop ≤ 2 pts, faithfulness ≥ X, p95 ≤ Y, abstention ≥ baseline, thresholds justified). The script exits pass or fail. Show **one failing candidate** (deliberately bad, e.g. 100/0 chunks) and **one passing**.
- [ ] **D1 Trace record:** one JSON line per query: trace id, timestamp, query, rewritten query, embedding model + version, collection, chunk ids + doc ids + doc versions + scores, filters, reranked order, prompt hash + full prompt, model + params, response, citations, guardrail actions, latency per stage, cache hit or miss. Written to **stdout** and to `/data/traces/traces.jsonl`.
- [ ] **D2 Trace tool:** `python -m tools.trace <id>` prints the exact context + prompt.
- [ ] **D3 Metrics summary:** top-1 similarity distribution, abstention rate, cache hit rate, p95 per stage, injection attempts flagged, over a time window.
- [ ] **D4 Guardrail logging:** the injection rail writes its action to the trace; tested with the Batch B injected doc.
- [ ] **D5 Root cause from a trace only** (Rehan drafts; **[M]** may edit): pick a wrong or abstained answer from B.
- [ ] **E1 Live queries** (draft in `eval/live_queries.jsonl`, **[M]** edits): ≥ 40 (≈ 28 in-domain, ≥ 12 from an uncovered topic) → `eval/live_queries.jsonl`.
- [ ] **E2 Coverage:** nearest golden question per live query, share above a justified threshold, uncovered queries grouped into topics.
- [ ] **E3 Drift:** ingest Batch B, re-run the suite, report what changed and why.
- [ ] **E4 Close the gap** (Rehan drafts ≥ 6 new golden questions; **[M]** may replace them): re-run, coverage rises; the script **exits non-zero** below the threshold.

## Day 4 · Fri 27 — Kubernetes (Part F) + report
- [ ] **F1** API Deployment, Chroma StatefulSet, Service; **PVC** for the data lake / quarantine / archive / traces.
- [ ] **F2** Ingestion + verification **Job** + **CronJob** (the only writer); **eval Job** `kubectl apply -f k8s/eval-job.yaml` writes to a volume and **fails when the gate fails**; gate thresholds in a **ConfigMap** → edit it and the outcome changes with no rebuild.
- [ ] **F3** Candidate = a **second Deployment + Service + its own collection**; eval Job against it; gate pass → rolling update (`maxUnavailable: 0`, `rollout status`); a candidate stopped by the gate; a bad release reversed with **`rollout undo`** → a new trace shows the **previous collection + embedding version**.
- [ ] **F4** Traces in `kubectl logs` + on the volume; metrics via `kubectl port-forward`.
- [ ] **F5** Requests and limits from `kubectl top` measurements (numbers go in the report).
- [ ] **k8s/README.md**: a fresh cluster → working pipeline. **README**: the exact command for each Part A–F.
- [ ] **Screenshots** **[M collects and labels them: A, B, C, D, E, F]**: terminal, command + output, nothing cropped.

## Day 5 · Sat 28 — Report + demo prep + submit
- [ ] **G Report PDF (≤ 8 pages + appendix)**:
  1. Figure 3 mapping table **[M]**
  2. Table 2 qualities table **[M]**
  3. Results tables / figures A–F + the release decision
  4. Short answers (a)–(f) (Rehan, with Malaika reviewing)
  5. Contribution table + 2–3 line AI statement **[M]**

  First page: names + roll numbers.
- [ ] **Demo rehearsal (both):** run the eval Job, open a trace, ingest an unseen batch with the ingestion Job. **Malaika practises explaining every part.**
- [ ] Final PR `a3 → dev → main`, both members' commits present, submit the repo URL + the report PDF.

---
### Cut order if time runs out
1. Reranker (not needed: our change is chunk size)
2. The typo variant of the noise test (do the irrelevant-docs variant only)
3. Fancy figures (tables are enough)

**Never cut:** Kubernetes for the demo, the 0-chunks re-run, the release gate pass + fail, rollout undo + trace, coverage exit code, committed result files.

## Progress notes
(Claude Code: append key decisions and known issues before each /clear.)
- 24 Nov (A0/A1): lake code in `indexer/pipeline/{lake,verify,ingest}.py`; run `cd indexer && LAKE_DIR=../data/lake OLLAMA_URL=http://localhost:11434 python -m pipeline.ingest --seed ../corpus/raw --report-dir ../eval/results`. doc_id comes from `doc_id:` in sources.yaml (both academic-rules entries share `academic-rules-undergrad`) else a slug of the name. Near-dup = mean of 3 embedded 1000-char windows (25/50/75%); first-2000-chars falsely flagged the two annual reports (0.975, shared cover pages). Real corpus max cross-doc cosine 0.885 → threshold 0.95. Recency fail = archive (superseded=true), not quarantine. Lake doc vectors in `vectors.json`. Indexer (`run.py`) still reads CORPUS_DIR: A2 must switch it to `verified/` + manifest.
- 24 Nov (A2): `pipeline/sync.py` (incremental, `--delete DOC_ID`), `pipeline/restore.py` (rollback). Chunk id = sha256(doc_id|version|idx|text)[:32]; manifest caches chunk_ids + chunk_sha256 + chunk_config so unchanged docs are not re-extracted. Chunk metadata now has `doc_id`. A newer version keeps the old one's chunks with superseded=true (paper: archive, don't delete). Evidence: `eval/results/a2-incremental-*.log` (413 chunks; rerun 0 embedded; change 7 embedded; delete 19 removed; rollback flips 14; orphans 0 throughout). First full sync ≈7 min on CPU. Local Chroma for testing: `docker run -d --name a3-chroma -p 8001:8000 chromadb/chroma:1.0.12`. `run.py` (A02 full rebuild) left as is; the K8s Job switches to ingest+sync in F2.
- 24 Nov (A3, Rehan's half): `scripts/make_batch_b_broken.py` generates 6 broken files into `data/batch_b/broken-*` (gitignored, rebuilt from corpus/raw): 2 exact dups, truncated PDF, corrupt PDF, mojibake txt, empty md. Seeding reads `<file>.meta.json` sidecars. All 6 quarantined (`eval/results/verification-20261124T182654Z.*`), 0 chunks embedded. Waiting on Malaika's text docs (near-dup, missing metadata, newer version, injected instruction, fillers) in `data/batch_b/*.md`, then re-run ingest + sync on the full batch and tick A3.
- 24 Nov (A3 done): Batch B = 12 docs in `data/batch_b/`: 6 generated broken files + 6 Rehan-drafted Markdown docs (each marked "synthetic test document"): newer faculty start-up policy 2026-11 (archives 2022-05; changed 6.1 two→three years, 9.3 workload exemption up to 3 cr hrs), near-dup of the grading page (cosine 0.989 → quarantined), lab safety with no front matter (missing metadata → quarantined), library notice with an injected instruction (verified + indexed on purpose: the D4 retrieval rail must catch it), 2 fillers (sports week, career fair). Lake after both batches: 14 live docs, 430 chunks, 0 orphans (`eval/results/a3-batch-b-*.log`). Golden questions on Batch B (faculty policy change) belong in E3/E4. Baseline for E3 drift: re-sync a collection from the lake without Batch B, or compare against eval results taken before this run — decide in B5.
- 25 Nov (Day 2 done): suite = `make suite` / `python eval/run_suite.py --label X [--collection C]` → `eval/results/<ts>-<label>.json` + table; `eval/compare.py A B` for diffs. Baseline `20261124T192554Z-baseline.json`: recall@5 0.96, MRR 0.87, nDCG@5 0.81, noise Δ nDCG -0.039; abstain on unanswerable 100%, false abstention 4% (h03), citation validity 100%, faithfulness 1.0 (23 judged), p95 13.5 s. Gemini rejects `seed` (400) → LLM_SEED sent to Groq only; eval runs at temperature 0, pace 8 rpm, retries; fallbacks (outages) reported separately, not scored. B4: retrieval identical across runs, 13 answers reworded, no verdict changed (`eval/results/b4-stochasticity.md`). Pending for Malaika: label `eval/labels/faithfulness_hand.jsonl` (10 rows, `label` = faithful/unfaithful) → judge agreement appears in the next run; review ≥ 8 synthetic golden questions. Note: these numbers include Batch B in the index; for E3 build a pre-Batch-B collection.
- 25 Nov (Day 3, known issue, report material): running heavy jobs in parallel on the 14 GB CPU laptop broke runs. (1) Killing a sync left orphan `tesseract` OCR processes, and two syncs competed for CPU: an OCR page took 3+ min, and a build looked hung for 20+ min. Fix: extraction is cached by sha256 in `<lake>/cache/` (`sync._extract_cached`), so re-chunking skips OCR. (2) The E3 sync (bulk embedding) ran beside two suite runs: query embeds to host Ollama passed the 30 s timeout (`httpx.ReadTimeout`), and both suites crashed at the e2e level after 20 min. Fix: the suite retries an embed timeout (5 s, 30 s). Rule: run one heavy job at a time (sync/OCR, embedding, suite). Gemini free RPM also limits suites to one at a time (8 rpm).
- 25 Nov (D1-D4): `services/tracing.py` writes one trace per query to stdout (`msg: trace`) and to `TRACE_FILE` (/data/traces/traces.jsonl). The trace holds the embed model + Ollama digest, collection, index_generation, filters, chunks with doc_id/version/score/boosted/dropped, the context, the full prompt + sha256, llm params/tokens, citations, guardrails, latency per stage and the cache. `services/guardrails.py`: query rail flags; retrieval rail drops chunks that carry instructions (`INJECTION_RAIL=drop|off`). `python -m tools.trace <id>` rebuilds the prompt and checks the hash; `python -m tools.metrics_summary --last N` gives the summary. C suites ran with `INJECTION_RAIL=off` so they match the baseline code path.
