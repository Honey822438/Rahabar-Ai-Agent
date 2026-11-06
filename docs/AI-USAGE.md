# AI usage

<!-- STARTER-TODO: list every AI tool you used. A specific disclosure carries no penalty. -->

| Tool | What it wrote or shaped | What we changed afterwards, and why |
| --- | --- | --- |
| Claude Code (Opus 5.5) | Used throughout this project. **Code:** the indexer pipeline, API, retrieval, generation, cache, tests and eval functions. **Infrastructure:** Dockerfiles, Kubernetes manifests, Makefile changes and the CI and CD workflows. **Documents:** first drafts of the ADRs, ARCHITECTURE, CORPUS, PIPELINE, engineering notes 1, 2, 3, 4 and 6, and the README. **Operations:** running the cluster and capturing the evidence in `docs/evidence/`. | Pending: the team reviews these and rewrites ADR 0001 in its own words |

Commit messages do not carry an AI attribution trailer. This file is the record of AI use.

## Malaika (i24-3098): golden set and corpus check

| Tool | What it did | What I verified myself |
| --- | --- | --- |
| Claude Code | Extracted text from the corpus PDFs and web pages, ran OCR on the two scanned PDFs (the 2023 rules and the faculty policy), searched all documents for "hostel", and drafted the candidate questions, expected answers, clause numbers, page numbers and quotes in `eval/golden.yaml`. It also re-checked the draft `docs/CORPUS.md` properties against the files. **The drafts came from the AI, not from me.** | See the line below. Quotes from the 2023 rules come from OCR and may contain small OCR errors. |

Automated check run by the AI assistant: all 19 quotes in `eval/golden.yaml` were matched against the extracted PDF and web-page text (the 2023 rules via OCR), and the file loads in `eval/run_eval.py` with 17 questions. This is a text match, not a human read of the PDFs.

Verified by Malaika: ___ of 17 questions
