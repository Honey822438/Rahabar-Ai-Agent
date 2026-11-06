# Indexing and retrieval pipeline

<!-- STARTER-TODO(3.3, 5.2): the chunking table, cache thresholds and evaluation results still need golden-set numbers. -->

## Extraction

`indexer/pipeline/extract.py` uses `pdfplumber`, runs OCR on any page with under 20 characters of text, and turns HTML tables into rows.

**Pages needing OCR, 41 in total** (from the Job's log):

| Document | Pages | OCR pages |
| --- | --- | --- |
| Faculty Entrepreneurship policy | 8 | 8 |
| Undergraduate Academic Rules (Aug 2023) | 26 | 24 |
| Academic Rules Handbook (Jun 2026) | 58 | 5 |
| Student Handbook (Jun 2026) | 64 | 4 |
| The other three PDFs | 123 | 0 |

**A table, before and after.** In the raw Fee Structure HTML, each value sits in nested markup. After extraction, each row keeps its label and amount together, so one chunk can answer the question:

```text
Before: <tr><td>Campus Transfer Fee</td><td>Rs. 5,000</td></tr>   (simplified)
After:  Campus Transfer Fee | Rs. 5,000
```

**What could not be recovered.** OCR on the scans leaves damage we did not repair. The first page of the Faculty Entrepreneurship policy yields stray fragments such as `REB`, `sls` and `BwWN ee`, and clause numbers separated from their text. The 2023 contents page reads `Academic Yeat`. Exact-term search on these scanned documents is therefore less reliable than on the 2026 handbook.

### Hidden off-page text

The two 2026 handbooks store text beyond the visible page: on a page 420 points wide,
`pdfplumber` returned words as far right as x = 800. By default it returns them, so a page's
text was interleaved with text belonging to another page. Nothing raised an error; it first
showed up as unrelated text inside retrieved chunks.

We first assumed two-column pages and wrote a column splitter, which changed nothing. The word
positions showed the real cause. The fix is `page.within_bbox(page.bbox)` in
`indexer/pipeline/extract.py`, which keeps only the visible page.

Page 6 of `academic-rules-handbook-jun-2026.pdf`, a table-of-contents page:

Before (clause 1.1 and its heading are mixed into the contents list):

```text
Academic Warning/Probation 18 1. Medium of Instruction
Repeating a Course 19
Late conduct of Examination/ Missed Examination 19
1. Introduction
Rechecking of Final Exams 20
6. Rules for Summer Semester 22
1.1 The medium of instruction and examinations for all courses is
7. Graduation Awards 24
English (except language courses, other than English, and
```

After (only what the page shows):

```text
Academic Warning/Probation 18
Repeating a Course 19
Late conduct of Examination/ Missed Examination 19
Rechecking of Final Exams 20
6. Rules for Summer Semester 22
7. Graduation Awards 24
```

## Cleaning

Rules in `indexer/pipeline/clean.py`, applied in this order:

1. Normalise ligatures, odd spaces and runs of whitespace inside a line.
2. Drop lines repeating at the top or bottom of at least 40% of pages, ignoring digits, so `2 Fast-Nuces` and `Fast-Nuces 9` count as one running header.
3. Drop bare page numbers.
4. Drop table-of-contents lines, which would otherwise out-rank the real clause.
5. Rejoin words hyphenated across lines and join wrapped lines into paragraphs.

**Deliberately kept:** clause numbers, headings and table rows, because citations and exact-term retrieval depend on them. A line starting like a clause is never treated as a running header (`clean.py:49`).

## Chunking
Method and reasoning are in ADR 0003. Size counts whitespace-separated words, as a stand-in for tokens.

Current provisional setting: 400/50, giving 372 chunks and a storage amplification of 1.05 (72,054 stored words / 68,604 original). The table below is filled once the golden set exists.

| Size (tokens) | Overlap (tokens) | recall@5 | Chunks stored |
| --- | --- | --- | --- |

## Embedding
`nomic-embed-text` through Ollama on the host, with 768-dimensional vectors, using the `search_document:` and `search_query:` prefixes. The pin is one key, `EMBED_MODEL` in `k8s/base/configmap.yaml:10`, read by both the API and the indexer.

The indexer records `embed_model` and `dimension` in the collection metadata (`indexer/pipeline/store.py:42-48`). The API compares them on every `/readyz` call, returns 503 and logs the conflict on a mismatch (`api/app/routes/health.py:17-26`). Evidence: `docs/evidence/embed-pin-mismatch.txt`.

## Semantic cache
Thresholds you tried, the false hit that ruled one out, the one you shipped.

## Evaluation method
How recall@k matches retrieved passages to golden ones (by source and section? by chunk id?).
