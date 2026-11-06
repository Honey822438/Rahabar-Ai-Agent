# PLAN.md — RAHBAR execution plan (Fri 6 Nov → Sun 8 Nov 2026, 23:59 PKT)

Built from the assignment PDF, `STARTER.md`, `scripts/check_submission.py`, `CLAUDE.md` and the first plan (`PLAN.original.md`).
**Team:** Malaika (i24-3098): 1.7 golden set, `docs/CORPUS.md`, UI branding in `ui/index.html`, manual testing notes, evidence screenshots, `docs/AI-USAGE.md`, PR reviews. Rehan Ahmed (i24-3012): everything else. Each reviews the other's PRs.
**Rules:** one task at a time. Tick `[x]` only when *Done when* has actually passed. Spec sections are shown as §. Late submissions are not accepted.

## Status
**Now:** 2.4 production steps. **Open:** 1.2 corpus must be named in the first PR; 2.5 must raise RELEVANCE_FLOOR above hostel scores (0.58-0.61 seen, floor is 0.5).
**Verified 6 Nov:** Docker 29.8.2, kubectl 1.37.1, kustomize, Python 3.12.16, Ollama 0.40.14 with `nomic-embed-text`.
**Missing:** `minikube`, `tesseract` and `gh`. CI installs its own `kubeconform`, `trivy` and `kind`.

## Blockers and open questions (user)
- [ ] **B1 Install minikube.** `CLAUDE.md` says it is installed, but it is not on PATH. It blocks 1.3.
- [x] **B2 Partner:** Malaika reviews; `main` keeps 1 required approval.
- [ ] **B3 Confirm default D1 and D2 below.** Work proceeds on these defaults unless changed.

## User-only tasks (Claude never handles keys)
- [ ] **U1** Create the GitHub repo, push, create `dev`, protect `main` (PR + CI required + 1 approval). Screenshot → `docs/evidence/`.
- [ ] **U2** Create a Gemini key in a new AI Studio project and put it in the gitignored `.env`. Cluster: `kubectl create secret generic rahbar-secret -n rahbar --from-literal=LLM_API_KEY="..."` (optionally `--from-literal=GROQ_API_KEY="..."`).
- [ ] **U3** Create a Docker Hub access token → GitHub Secrets `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`. Needed by Saturday evening.
- [ ] **U4** Run `make cluster` and `OLLAMA_HOST=0.0.0.0 ollama serve`, approve PRs, take the GitHub screenshots, submit on Classroom.
- [ ] **U5** `sudo apt install tesseract-ocr` for local indexer runs (the image installs its own).

## Decisions that fill gaps or conflicts
| # | Problem | Decision |
|---|---|---|
| D1 | The cache must be flushed on re-index, but §4.7 says Redis accepts traffic **from api only**, so the indexer can't flush it. | The indexer writes `index_generation` to the collection metadata. The API keys cache entries by generation and deletes old ones when it changes. |
| D2 | The `CLAUDE.md` NetworkPolicy allows Groq HTTPS but not Gemini, the primary provider. Google IPs also change. | api egress: 443 to `0.0.0.0/0` except private ranges. Indexer gets the same only if fetching the corpus needs it. |
| D3 | `PLAN.original.md` 2.3 says Groq; `CLAUDE.md` says Gemini. | `CLAUDE.md` wins: Gemini first, Groq only if its key exists. |
| D4 | Tuning could burn Gemini's low free quota. | Chunking and cache tuning use retrieval only, with the stub LLM. Gemini runs only for final evals. |
| D5 | The real corpus and the CI fixtures can't share a baseline. | `eval/baseline.json` = real corpus (submitted). `eval/baseline.fixture.json` = CI gate. Add a `--baseline` flag if needed. |
| D6 | CI has no Gemini key on PRs, and must not need one. | e2e-eval uses Ollama + `nomic-embed-text` on the runner and the stub LLM. Abstention therefore rests on the relevance floor, which is enforced in code before any LLM call. |
| D7 | PDFs aren't committed, so CI-built images can't contain them. | Indexer init container runs `fetch.py` into a corpus PVC and skips files whose hashes match. CI mounts fixtures from a ConfigMap instead (`k8s/overlays/ci`). |
| D8 | A failed re-index must not destroy the working index. | Build a new collection, verify its count, then swap it to the live name. Confirm rename works on Chroma 1.0.12. |

## Friday — foundation, stubs on Kubernetes, corpus
- [x] **1.1 Repo.** Unzip the kit as the first commit, keeping `CLAUDE.md` and `PLAN.md`. Add `LICENSE`, then `git init` and create `dev`. Use conventional commit prefixes from here on (checker: 25+ commits).
  *Done when:* `make install && make test && make lint` pass (11 tests).
- [ ] **1.2 Corpus check first (§2).** The 2023 rules PDF "would not open" when the spec was written, and the version pair is the most common weak choice. Run `pdffonts` to confirm the scan. If 2023 is dead, use another genuine pair (Prospectus 2026 vs Handbook, or annual report editions). Write `sources.yaml`, run the fetch, commit `MANIFEST.md`.
  *Done when:* ≥6 docs and ≥40 pages download; `fetch.py --verify` passes; the corpus is named in the first PR (§2 approval).
- [x] **1.3 Dockerfiles (§10).** api, indexer (with tesseract), ui. Pinned bases, non-root `USER`, exec-form `CMD`; `.dockerignore` lists `.git`, `__pycache__`, `.venv`, corpus.
  *Done when:* all 3 build; `docker run` api answers `/healthz`.
- [x] **1.4 Cluster.** `make cluster` (B1, U4). Free memory first: only about 6 GB is available and minikube alone takes 6 GB.
  *Done when:* node Ready; calico, metrics-server and ingress running.
- [x] **1.5 Manifests on stubs (§4).** All objects in `k8s/base` + overlays, ConfigMap `RETRIEVER=stub`, `LLM_PROVIDER=stub`, `EMBED_MODEL=dummy-768`, Job `--dummy`. Traps to handle:
  - `chromadb/chroma:1.0.12`, and verify Chroma and Redis run under `runAsNonRoot` + `readOnlyRootFilesystem` (set UID and `fsGroup`).
  - `secret.placeholder.yaml` is committed with `REPLACE_ME` and **never listed in kustomization**.
  - Jobs are immutable: use `ttlSecondsAfterFinished` so re-applying doesn't fail. CronJob uses `concurrencyPolicy: Forbid`.
  - Requests and limits on every container, **including init containers**.
  *Done when:* pods Running/Completed; Ingress serves `/` and `/api/ask`; HPA shows a real %, not `<unknown>`.
- [x] **1.6 NetworkPolicy (§4.7).** Default deny + the allow list, with DNS egress.
  *Done when:* from `ui`, chroma is unreachable; from `api`, chroma and redis work; DNS resolves. Save the output.
- [ ] **1.7 Golden set (§5.1), before any tuning.** `eval/golden.yaml` with ≥15 questions: 8 ordinary, 2 version, 2 exact-term, 2 must-abstain, 1 injection. Each has its doc + section, taken from reading the PDFs, not from retrieved chunks.
- [ ] **1.8 First PR** `dev` → `main`, naming the corpus (needs U1). Start `docs/AI-USAGE.md` and a running log for Engineering Note 7 (a real failure that cost over an hour).

**Friday checkpoint:** the stub system works through the Ingress on minikube.

## Saturday — real RAG, then CI/CD
- [x] **2.1 Indexer (§3.1).** `extract` (pymupdf; OCR pages with no text; strip repeating headers/footers; keep headings; also read `.md` + front matter for fixtures), `clean`, `chunk` (sections → paragraphs → sentences + overlap), `embed` (prefixes, batched), `store` (metadata `source, section, page, doc_version, superseded`; collection metadata `embed_model, dim, index_generation`; D8).
  *Done when:* runs locally; logs chunk count and storage amplification; retrieves a known clause.
- [x] **2.2 Retriever (§3.2).** `ChromaRetriever`: same model + query prefix, top_k, `superseded=false` unless an older version is explicitly asked for, returns scores.
- [x] **2.3 Generation (§3.4–3.5).** Hosted provider per `CLAUDE.md` (confirm the model name on the first call, JSON mode, timeout), `ollama-host`, delimited numbered evidence. In code: relevance floor → abstain, validate → retry once → canned fallback (never a 500), citation check that drops anything not in `retrieved`.
  *Done when:* tests cover abstention, fallback, a fabricated citation and a **poisoned chunk**, all with stubs.
- [ ] **2.4 Production steps (§3.2–3.3, 4.3–4.4, 4.8).** Redis semantic cache + skip rules (follow-ups, abstentions, out-of-scope, failed validation) + D1, turn storage, `/readyz` naming the failure, embed-pin check, metrics, per-request log line.
  *Done when:* unit tests pass, coverage ≥60%, ≥12 tests in total.
- [ ] **2.5 Eval code + tuning (§3.1, 3.3, 5).** The 4 functions in `run_eval.py`. Run **3 (size, overlap) configs**, recall@3/@5 overall and by type (D4). Add keyword boost only if exact-term recall is poor. Choose the cache threshold: lowest with zero false hits, recording the false hit that ruled one out.
- [ ] **2.6 Switch the cluster to real.** Do the pin demo **first**: set the real `EMBED_MODEL` without re-indexing → 0/1 READY + log line, save evidence. Then add the secret (U2), Ollama `ipBlock` and D7, and re-index.
  *Done when:* through the Ingress, one question gets a cited answer and an absent topic abstains.
- [ ] **2.7 ci.yml (§6).** lint → test → manifests (`kubeconform -strict`) → build (no push) → Trivy → e2e-eval (kind + ingress-nginx + `overlays/ci`, D5, D6). Least-privilege `permissions:`.
  *Done when:* green on a PR. The e2e job is the hardest part, so start it by 18:00.
- [ ] **2.8 cd.yml (§6).** test → build-push (`needs:`, `${{ github.sha }}`) → deploy (`needs:`, ephemeral cluster, `rollout status`, smoke test through the Ingress). Needs U3.
  *Done when:* a successful run exists on `main`. **This link is a required deliverable, so don't leave it to Sunday night.**

**Saturday checkpoint:** a stranger's flow (§1.3) works, and CI is running.

## Sunday — prove it, write it, submit
- [ ] **3.1 Final eval on Gemini.** Pace requests to the rate limit. Must-abstain 100%, citation validity ≥95%. Commit `eval/baseline.json` + `results.json`.
- [ ] **3.2 Gate demo.** PR that fails the gate → screenshot the blocked merge → fix → screenshot green (U4).
- [ ] **3.3 Cluster evidence (§4.5–4.6) → `docs/evidence/`.** `kubectl top pods` including indexer peak (then tune requests/limits from it), endpoints with 3+ IPs, HPA, `set image` → `rollout status` → `rollout undo` with a visible change, delete a pod with nothing breaking.
- [ ] **3.4 Failure analysis (§5.5).** A no OCR, B 100-token no overlap, C top_k 1, E no superseded filter. Each: symptom, diagnosis, stage, remedy, and the metric or log line that would have shown it.
- [ ] **3.5 Docs, with real numbers and file:line references.**
  - ADRs: `0001-indexer-as-job` (**the user should write or rewrite this in their own words; the spec requires it and it's read first**), `0002` cache, `0003` chunking, `0004-llm-provider-and-data-governance` (includes what the free tier means for student questions).
  - `CORPUS.md` (7 properties), `PIPELINE.md`, `ARCHITECTURE.md` (why StatefulSet), `ENGINEERING-NOTES.md` (7 questions), `AI-USAGE.md`.
  - `README.md` replaced: mermaid diagram, CI badge, API table, secret command, apply order, indexer command.
- [ ] **3.6 Clean-clone test.** Fresh clone + fresh `minikube delete && make cluster`, following only the README.
  *Done when:* §1.3 passes end to end.
- [ ] **3.7 Submit by 22:00 (buffer).** `check_submission.py` has no failures; zero `STARTER-TODO`; history scanned for keys (`git log -p | grep -E 'AIza|gsk_'`). Submit the repo URL (public, or instructors added), cd.yml run link, Docker Hub SHA tags link, eval files.

## If time runs out
**Cut first:** `ollama-incluster` → hybrid retrieval (explain it in the notes) → extra failure-analysis detail (keep 4 stages) → Groq fallback.
**Never cut:** secrets hygiene, namespace, indexer Job, citation check, abstention, requests/limits, embed pin, PVCs, `needs:` + SHA tags, a working README, the cd.yml run.

## Known risks
| Risk | Response |
|---|---|
| Laptop memory (14 GB; about 8 GB already in use) | Close other apps; tune limits from `kubectl top`. |
| Gemini rate limits during eval | D4, pacing, the Groq fallback if the key exists. |
| nu.edu.pk down or a file changed | Fetch early and keep `corpus/raw/`; the hash check shows any change. |
| Ollama unreachable from pods | Check `OLLAMA_HOST=0.0.0.0` and the `ipBlock` for the IP in `host.minikube.internal`. |
| e2e-eval in CI takes too long to get working | Started Saturday; keep `eval/fixtures` small. |

## Progress notes
(Append key decisions, known issues and real failures here before each /clear.)
- 1.2 findings: 9 docs, 279 PDF pages. The 2023 rules (26 pages, 243 chars of text) and the entrepreneurship policy (8 pages, no fonts) both need OCR, so the version pair depends on OCR working. The pair is genuine: CGPA 2.00 is clause 1.26 in 2023 and 1.25 in 2026. Hostels are only mentioned in the annual reports and Student Handbook, so must-abstain questions should ask for hostel rules or fees, not whether hostels exist.
- Note 7 candidates: (a) a Service named `chroma` injects `CHROMA_PORT=tcp://...`, which crashes the Chroma server; fixed with `enableServiceLinks: false`. (b) minikube runs containerd and `minikube image load` failed on the indexer with Docker 29; `make images` now uses `minikube image build`.
- Q7 raw material, CHROMA_PORT bug (6 Nov): **Symptom:** `chroma-0` in CrashLoopBackOff, 6 restarts, while api, redis and ui were healthy. **Prime suspect beforehand (not a tested guess):** the non-root/read-only securityContext, which 1.5 had listed as a Chroma risk. **What revealed it:** `kubectl logs chroma-0`: `Error loading config: invalid type: found string "tcp://10.100.217.229:8000", expected u16 for key "PORT" in CHROMA_ environment variable(s)`. **Cause:** Kubernetes injects `CHROMA_PORT` for a Service named `chroma`, and Chroma reads `CHROMA_*` as config. **Fix:** `enableServiceLinks: false`. **Caveat:** this took minutes, not over an hour, and the log line pointed straight at it, so Q7 needs a longer failure if one happens.
- Q7 candidate, handbook text (6 Nov): retrieved chunks mixed unrelated text. Wrong first belief: two-column pages, so a column splitter was written and it changed nothing. What revealed it: `extract_words()` showed x up to 800 on a 420-wide page, so the PDFs hold hidden text beyond the visible page. Fix: `page.within_bbox(page.bbox)`. Time spent was under an hour, so note that honestly.
