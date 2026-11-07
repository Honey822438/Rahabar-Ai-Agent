# Failure analysis

We broke four stages one at a time, on a separate local Chroma with the shipped code otherwise unchanged. The cluster was not touched, so nothing needed restoring there.

Each run measured retrieval only, without Gemini, to save quota. So symptoms below are what was retrieved; we did not generate an answer for each failure. A healthy 400/50 control gave recall@5 of 1.00 on the 15 answerable golden questions.

| Stage | What we broke | recall@5 | Would the gate catch it? |
| --- | --- | --- | --- |
| A · Extraction | No OCR | 1.00 | **No** |
| B · Chunking | 100 words, no overlap | 1.00 | **No** |
| C · Retrieval | `top_k` 1 | 0.80 | Yes |
| E · Source | No superseded filter | 1.00 | **No** |

**The main lesson:** three of the four failures leave recall@5 unchanged, so our golden set can't see them. That makes recall alone a poor health check, and it is a real gap in the gate.

## Stage A · Extraction
- **What we broke:** replaced the OCR step with one returning no text, then re-indexed.
- **Symptom:** the scanned policy disappeared from the index. Asked "Can full-time faculty members start a technical start-up?", the top 3 were all annual report chunks (top score 0.65). With OCR, all 3 were from the policy (0.80). The index fell from 413 to 337 chunks.
- **Diagnosis, as if we had not caused it:** the indexer's per-document log line shows `"source": "faculty-entrepreneurship-...pdf", "pages": 8, "words": 0, "chunks": 0`, and the 2023 rules drop to 21 words. Total `original_words` fell from 68,629 to 61,788. `ocr_pages` still reads 8 here, because it counts pages attempted, so it is `words` that reveals this.
- **Remedy:** restore OCR. Make the Job fail, or at least warn, when a document yields no chunks. Add a golden question that only the scanned policy can answer, since none exists now.

## Stage B · Chunking
- **What we broke:** set `CHUNK_SIZE=100`, `CHUNK_OVERLAP=0`. Our chunker still respects sections and sentences, so this is smaller than the spec's plain fixed-size split, and milder.
- **Symptom:** recall stayed at 1.00, but the index grew from 413 to 986 chunks and embedding took about the same time (451 s against 441 s). q12 fell from rank 1 to rank 2, behind "Scheduling of Classes". With no overlap, a rule spanning a boundary would be split, though no golden question exposed that.
- **Diagnosis, as if we had not caused it:** the `chunking finished` log line shows the jump in chunks. Per-request logs show chunk ids and scores, where shorter chunks crowd the top 5 with neighbouring pieces of a section.
- **Remedy:** restore 400/50 in the ConfigMap and re-index. Add a golden question whose answer spans two sentences far apart in one clause.

## Stage C · Retrieval
- **What we broke:** retrieved with `top_k` 1.
- **Symptom:** recall@5 fell to 0.80, with ordinary questions at 7 of 10. q05, q06 and q07 lost their correct passage. q06, about MS students, got only the undergraduate-focused "Academic Warning/Probation" chunk rather than the grading page. Exact-term and version questions still passed.
- **Diagnosis, as if we had not caused it:** `eval/results.json` shows the fall by type, and it breaches the gate's 5-point limit. Each request's log line shows `top_k: 1` and a single chunk id.
- **Remedy:** restore `TOP_K` to 5 in the ConfigMap and restart the API.

## Stage E · Source
- **What we broke:** removed the `superseded` filter from the Chroma query.
- **Symptom:** the repealed 2023 rules outranked the current ones on both version questions. For q11, the top hit became the 2023 summer semester section (0.86, over 2026's 0.84); for q12, the top two became 2023 chunks (0.84, 0.82, over 0.79). The 2023 text says "8 to 9 weeks" where the current rule says 8 weeks, so a student could be given a repealed rule. Recall stayed at 1.00, because the 2026 passage was still in the top 5.
- **Diagnosis, as if we had not caused it:** the response's `retrieved` list and the citations name `undergraduate-academic-rules-aug-2023.pdf` for a question that did not ask about an older version. The `expect` check on these questions could show it in the answer, but it is not part of the gate.
- **Remedy:** restore the filter (`api/app/retrieval/chroma.py`). A unit test already covers it. Add a gate check that no superseded source appears in the retrieved list for current-version questions.
