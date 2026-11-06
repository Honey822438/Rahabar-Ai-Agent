# CLAUDE.md — RAHBAR (Assignment 02: Grounded RAG on Kubernetes)

## What this is
A grounded question-answering service over a real FAST-NUCES document corpus. It answers only from the indexed documents, cites [source / section / page], abstains when the corpus doesn't cover a question, and runs on **minikube** as ~15 Kubernetes objects with CI/CD.
**Deadline: Sun 8 Nov 2026, 23:59 PKT.** Work started Fri 6 Nov. Time is the main constraint: prefer simple, graded-correct solutions over clever ones.

The assignment PDF is the spec. Read `STARTER.md` and `docs/*` templates. Every `STARTER-TODO(x.y)` marks graded work; none may remain at submission (`python scripts/check_submission.py`).

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
