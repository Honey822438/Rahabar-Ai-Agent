# CLAUDE.md — RAHBAR (Assignment 02: Grounded RAG on Kubernetes)

## Team & ownership
| Owner | Tasks | Notes |
|---|---|---|
| Rehan Ahmed (i24-3012) | Dockerfiles, all K8s manifests, minikube cluster, indexer pipeline, retrieval, generation, cache, /readyz, embed pin, ci.yml, cd.yml, 2.5 tuning (floor, cache threshold, 3 chunking configs), eval code (run_eval.py), baseline, gate demo, cluster evidence, FAILURE-ANALYSIS, ADRs, ARCHITECTURE, PIPELINE, ENGINEERING-NOTES, README, final checker + submission | Don't touch Malaika's files without asking |
| Malaika (i24-3098) | 1.7 golden set (eval/golden.yaml), CORPUS.md review, ui/index.html branding (no API changes), manual test notes (docs/evidence/manual-test-notes.md), PR reviews/approvals, her section in AI-USAGE.md | Works on branches → PR into dev; commits from her own account |
| Both | Read and understand ADRs + ENGINEERING-NOTES; AI-USAGE.md honest; no secrets; no push to main | |

If you are Malaika's Claude Code: read HANDOFF-MALAIKA.md first, work only on Malaika's tasks, never modify k8s/, api/, indexer/ or workflows unless she explicitly asks, and never push to main.

## What this is
A grounded question-answering service over a real FAST-NUCES document corpus. It answers only from the indexed documents, cites [source / section / page], abstains when the corpus doesn't cover a question, and runs on **minikube** as ~15 Kubernetes objects with CI/CD.
**Deadline: Sun 8 Nov 2026, 23:59 PKT.** Work started Fri 6 Nov. Time is the main constraint: prefer simple, graded-correct solutions over clever ones.

The assignment PDF is the spec. Read `STARTER.md` and `docs/*` templates. Every starter placeholder marker marks graded work; none may remain at submission (`python scripts/check_submission.py`).

## Machine
- **Already installed by the user:** Docker, kubectl, minikube, kustomize-capable kubectl, Ollama. Don't reinstall them; just verify versions.
- **The user does these by hand:** create the GitHub repo + branch protection, create the Gemini key. Never ask for a key in chat. For local runs the key goes in a gitignored `.env`; on the cluster, the user runs `kubectl create secret ...` themselves.
- Ubuntu laptop, 14 GB RAM, CPU only. minikube: `--driver=docker --cni=calico --memory=6144 --cpus=4`, addons `metrics-server`, `ingress`.
- Python 3.12 venv (`make install`). System Python is 3.14; don't use it. Conda `(base)` must be deactivated.
- Ollama runs on the host (`OLLAMA_HOST=0.0.0.0 ollama serve`) with `nomic-embed-text` pulled. The cluster reaches it at `host.minikube.internal:11434`.

## Key decisions (do not change without asking)
| Area | Decision |
|---|---|
| Generation | `LLM_PROVIDER=hosted` → **Google Gemini free tier** via its OpenAI-compatible endpoint `https://generativelanguage.googleapis.com/v1beta/openai/`, model `gemini-flash-lite-latest` (verify the exact name on first call). Key `LLM_API_KEY` in K8s Secret `rahbar-secret`, its own AI Studio project (not shared with other projects). JSON mode + Pydantic validation, retry once, then canned fallback. **Optional Groq fallback** (`GROQ_API_KEY` in the same Secret; `openai/gpt-oss-20b` → `qwen/qwen3.8-27b`, `tool_choice="none"`) used only if that key exists, because Gemini's free requests-per-minute are low. `ollama-host` is the secondary mode. |
| Embeddings | `EMBED_MODEL=nomic-embed-text` via host Ollama, with `search_document:` / `search_query:` prefixes. Pinned in one ConfigMap key read by both api and indexer. |
| Vector DB | Chroma **StatefulSet**, 1 replica, `volumeClaimTemplates`. ClusterIP only. |
| Cache | **Redis** Deployment + PVC (ADR 0002). Cosine threshold from the ConfigMap, chosen by data. Never cache follow-ups, abstentions, out-of-scope answers or failed validations. **Flush on re-index.** |
| Indexing | Only the **Job** / **CronJob** writes Chroma. The API only reads. The indexer writes `embed_model` + `dim` into the collection metadata; the API refuses readiness on a mismatch and logs the conflict. |
| Retrieval | top_k from the ConfigMap; metadata filter `superseded=false` unless the question explicitly asks about an older version; relevance floor → abstain. Consider light hybrid (keyword boost for exact terms like clause numbers, course codes, CGPA) if exact-term recall is poor. |
| Temperature | 0.2 (facts + JSON), justified in a ConfigMap comment. |

## Non-negotiables (each is an automatic deduction)
- No secret, key or password in Git, ever. `*-secret.yaml` gitignored; committed manifests hold placeholders. Never print keys.
- Everything in namespace `rahbar`. Never `default`.
- Indexing never at API startup.
- Every citation must match a chunk actually retrieved for that request (code-checked before returning).
- Must-abstain questions → `answered_from_context: false` (100%).
- Chroma / Redis never NodePort or LoadBalancer; both have PVCs.
- Every container (including Job and CronJob) has requests + limits. HPA must never read `<unknown>`.
- CI: `needs:` on every publish/deploy job; deploy by commit SHA, never `:latest`; least-privilege `permissions:`.
- README apply order must work from a clean clone.
- No direct pushes to `main` (PRs from `dev`).

## Kubernetes objects (k8s/base + overlays/dev,prod via kustomize)
Namespace, Deployment api (3 replicas, startup/liveness/readiness probes, `maxSurge:1 maxUnavailable:0`, preStop sleep, terminationGracePeriodSeconds), Deployment ui (nginx), StatefulSet chroma, Deployment + PVC redis, Job indexer (`restartPolicy: OnFailure`, `backoffLimit`), CronJob reindex (weekly, same image/args), 4 ClusterIP Services, Ingress (`/` → ui, `/api` → api), ConfigMap, Secret (placeholder only), NetworkPolicy (default deny + allow: ingress→ui, ingress/ui→api, api+indexer→chroma, api→redis, DNS egress to kube-system 53 UDP/TCP, api+indexer egress to the host Ollama ipBlock and to Groq HTTPS), HPA (api, min 3, max 8, CPU). Per-workload ServiceAccount, `automountServiceAccountToken: false`, `runAsNonRoot`, `readOnlyRootFilesystem`, drop ALL capabilities (writable `emptyDir` for /tmp where needed).
Probes: `/healthz` touches nothing; `/readyz` = Chroma reachable + collection non-empty + Redis reachable + embed pin matches, else 503 naming the failure.

## Observability
JSON logs to stdout with `request_id` (from `X-Request-ID` or generated). One log line per request: top_k, retrieved chunk ids, scores, abstained?, cached?, provider/model. `/metrics`: request count + latency, retrieval latency, generation latency, cache hit ratio, abstentions, fallbacks, tokens in/out.

## Working style
- One PLAN.md task at a time: state the plan in 3–5 lines, build, run the "Done when" check, report in **max 3 lines**.
- Tests use stub providers (no network) for CI; coverage ≥ 60% on the app package.
- Add new config keys to both `api/app/config.py` / `indexer/pipeline/config.py` and the ConfigMap.
- Ask before: changing the decisions table, deleting files, or anything that costs money.
- If blocked for long, propose the simplest workaround that still meets the spec.
- Record AI assistance honestly in `docs/AI-USAGE.md` as you go.

## Commands
```bash
make install && make test && make lint     # local, stubs
make dev                                   # API + UI with stubs on :8000
make cluster                               # minikube with calico + addons
eval $(minikube docker-env)                # or: minikube image load <img>:<tag>
kubectl apply -k k8s/overlays/dev
kubectl create job --from=cronjob/reindex manual-reindex-1 -n rahbar
python eval/run_eval.py                    # golden-set eval against the live stack
python scripts/check_submission.py         # before submitting
```

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
| **Rehan (i24-3012)** | All code, scripts, manifests, runs, results, report results + short answers; drafts of every input (golden set, pairs, live queries, Batch B, E4 questions, D5) |
| **Malaika (i24-3098)** | Edits / replaces Rehan's drafts: ≥ 8 hand-written golden questions (`source: human`) and reviews ≥ 8 synthetic ones (`reviewed: true`), edits `eval/pairs/*` and `eval/live_queries.jsonl`; writes the ≥ 8 hand faithfulness labels (`eval/labels/*`); report tables 1, 2, 5; screenshot collection. Optional: improve the Batch B text docs and the D5 draft |

**Rule: Malaika's work never blocks or breaks ours.** Every input she owns has a working draft (by Rehan / Claude Code, labelled `source: synthetic`, `reviewed: false`) that the pipeline uses now; she improves it later. Only questions a human wrote count as `human`. `scripts/validate_inputs.py` runs in CI on PRs into `dev` and `main`, so a malformed edit fails the PR, not the pipeline.

If you are **Malaika's Claude Code**: work only on her tasks above; edit only `eval/golden.jsonl`, `eval/live_queries.jsonl`, `eval/pairs/*`, `eval/labels/*`, `data/batch_b/*.md|txt`, `report/*`. Never touch code, `k8s/` or workflows. Never push to `main`. No Co-Authored-By trailers.
