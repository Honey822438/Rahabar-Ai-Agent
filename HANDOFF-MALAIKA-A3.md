# Handoff for Malaika: Assignment 03 (RAGOps)

**Due Sat 28 Nov.** Please finish **Tasks 1–3 by Thursday night** and **Tasks 4–5 by Friday evening**.
Team: Rehan (i24-3012) builds the code and Kubernetes. **Malaika (i24-3098)** does review, labelling and report writing (below).
**Both of us must explain every part at the demo**, so read `PAPER-NOTES.md` and `PLAN-A3.md` once.

## 0. Setup (once)
```bash
cd Rahabar-Ai-Agent            # your existing clone (or git clone https://github.com/Honey822438/Rahabar-Ai-Agent.git)
git fetch origin
git checkout a3 && git pull origin a3
git checkout -b malaika-a3     # your own branch
git config user.name  "Malaika ..."           # your real name
git config user.email "your-github-email"     # same as your GitHub account
```
Commit small and often (one commit per finished piece). When a task is done: `git push -u origin malaika-a3` and open a **PR into `a3`** (not `main`). CI checks your files with `scripts/validate_inputs.py`. If it fails, fix the format and push again.

## 1. What's already built (so you can explain it)
- **Part A:** new documents are **verified** (quality, completeness, recency, duplicates) before indexing. Bad ones go to **quarantine**. Re-running on unchanged data embeds 0 chunks. Old versions are **archived** and can be restored. **Batch B** = 12 test docs with planted problems.
- **Part B:** one command (`make suite`) tests at **3 levels**: embeddings (paraphrase vs unrelated similarity), retrieval (recall@3/5, MRR, nDCG@5, noise test), answers (faithfulness, abstention, citations, latency). Results are in `eval/results/`.
- **Part C:** candidate change = chunk size 600 (`rahbar_c600`, passes the gate); bad candidates top_k=1 / chunks 100 (fail). Gate rules are in `config/gate.yaml`.
- **Part D:** every question writes a **trace** (JSON line). `tools/trace.py <id>` rebuilds the exact prompt.
- **Part E:** 40 "live" queries vs the golden set. Coverage was **60% before**, **85% after** adding 8 new questions.
- **Part F (in progress):** everything runs on Kubernetes (minikube).

## 2. Your tasks

### Task 1: faithfulness hand labels ⏰ Thursday
File: `eval/labels/faithfulness_hand.jsonl` (about 10 lines). Each line has a question, the retrieved context and the answer, plus an **empty label**.
For each line: read the context and the answer. Is **every claim in the answer supported by the context?**
- Fill the label field with **yes / no** (use the exact field name and values already in the file), and a short reason if there's a reason field.
- **Judge it yourself. Don't let AI decide the label.** This is the "human" check against the AI judge.

### Task 2: review 8 synthetic golden questions ⏰ Thursday
File: `eval/golden.jsonl`. Pick **8 lines with `"source": "synthetic"`** (from the original 14, not the E4 ones).
For each: open the PDF it points to (document + page), check that the question makes sense, the page and section are right, and the expected answer is right. Fix anything wrong, then set **`"reviewed": true`**.
Don't change `"source"`. Synthetic stays synthetic.

### Task 3: review the 8 new E4 questions ⏰ Thursday
Also in `eval/golden.jsonl`: the 8 questions added for Part E (grade meaning, refund/leave, plagiarism, FYP, degree correction fee…). Same check as Task 2, then set `"reviewed": true`.
If a topic is **not** in our documents at all, the question must be marked **unanswerable** (should abstain). Tell Rehan if you change a type.

### Task 4: D5 root cause from one trace ⏰ Friday
Rehan will give you **one trace id** for a wrong or abstained answer. Run:
```bash
python -m tools.trace <trace_id>        # or the command in README "Part D"
```
Using **only that trace**, write **5 lines** in `report/d5-root-cause.md`: the question, what went wrong, which chunk / document version / filter caused it, the evidence in the trace, and the fix.

### Task 5: report tables + statement ⏰ Friday
In `report/` (create the folder), one file each:
1. `report/table1-figure3-mapping.md`: one row per Figure 3 stage (**ingest, verify, update data lake, update retrieval sources, offline testing, live testing, check coverage**), with the columns *what our pipeline does · the file that does it · what is missing*. Use `PAPER-NOTES.md` and `PLAN-A3.md`, and ask Rehan or Claude Code for the file names.
2. `report/table2-qualities.md`: one row per quality (**adaptability, monitorability, observability, traceability, reliability**), with the columns *what we measure · our threshold · the evidence (file / result)*. Thresholds are in `config/gate.yaml`, numbers in `eval/results/`.
3. `report/contribution.md`: who did what (be honest), plus a **2–3 line AI statement** (e.g. "We used Claude Code / Claude to help write code, scripts and drafts; we reviewed, labelled and verified the results ourselves.").

### Task 6 (Saturday): screenshots + demo practice
Rehan will run the commands. You save and label the screenshots (A, B, C, D, E, F) for the report appendix, and practise explaining each part.

## 3. What you may and may not touch ⚠️
**You may edit ONLY:**
- `eval/labels/faithfulness_hand.jsonl`
- `eval/golden.jsonl` (only the `reviewed` field and fixes to your reviewed questions)
- `report/*` (new files)

**Do NOT change anything else**, including `api/`, `indexer/`, `eval/*.py`, `scripts/`, `tools/`, `k8s/`, `config/`, `.github/`, `Makefile`, `CLAUDE.md`, `PLAN-A3.md`, `README.md`, and results files.
Never push to `main`. Never commit keys or `.env`. No `Co-Authored-By` trailers.
Before every commit, run `git status` and check that only allowed files changed.

## 4. First message for your Claude Code
```
I'm Malaika (i24-3098). Read HANDOFF-MALAIKA-A3.md, CLAUDE.md (Assignment 03 section), PLAN-A3.md and PAPER-NOTES.md.
HARD RULE: edit ONLY eval/labels/faithfulness_hand.jsonl, eval/golden.jsonl (reviewed field + fixes to questions I review) and report/*. Never touch code, scripts, k8s, config or workflows; if a task seems to need another file, stop and ask me. Never push to main, no Co-Authored-By trailers, show me git status before every commit.
Start with Task 1: show me each item in faithfulness_hand.jsonl one at a time (question, context, answer). I decide the label myself; you only write what I say. Then Task 2 and Task 3: for each question, show me the document + page so I can check it, then set reviewed: true when I confirm. Run scripts/validate_inputs.py before each commit. Max 5 lines per reply.
```
