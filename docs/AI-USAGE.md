# AI usage

| Tool | What it wrote or shaped | What we changed afterwards, and why |
| --- | --- | --- |
| Claude Code (Opus 5.5) | Used a little bit in project **Code:** the indexer pipeline, API, retrieval, generation, cache, tests and eval functions. **Infrastructure:** Dockerfiles, Kubernetes manifests, Makefile changes and the CI and CD workflows. **Documents:** first drafts of the ADRs, ARCHITECTURE, CORPUS, PIPELINE, engineering notes 1 to 7, and the README. **Operations:** running the cluster and capturing the evidence in `docs/evidence/`. | ADR 0001 and Engineering Note Q7 edited by us; see the line below |

ADR 0001 and Engineering Note Q7 were drafted with Claude (chat) from our project facts, then edited by us.

Commit messages do not carry an AI attribution trailer. This file is the record of AI use.

## Malaika (i24-3098): golden set and corpus check

| Tool | What it did | What I verified myself |
| --- | --- | --- |
| Claude Code | Extracted text from the corpus PDFs and web pages, ran OCR on the two scanned PDFs (the 2023 rules and the faculty policy), searched all documents for "hostel", and drafted the candidate questions, expected answers, clause numbers, page numbers and quotes in `eval/golden.yaml`. It also re-checked the draft `docs/CORPUS.md` properties against the files. **The drafts came from the AI, not from me.** | See the line below. Quotes from the 2023 rules come from OCR and may contain small OCR errors. |

Automated check run by the AI assistant: all 19 quotes in `eval/golden.yaml` were matched against the extracted PDF and web-page text (the 2023 rules via OCR), and the file loads in `eval/run_eval.py` with 17 questions. This is a text match, not a human read of the PDFs. The AI assistant also looked at rendered page images for the two version questions (q11, q12) and confirmed both the 2023 and 2026 wording and the printed page numbers (2023: pp. 15 and 9; 2026: pp. 22 and 13).

Verified by Malaika: 17 of 17 questions
