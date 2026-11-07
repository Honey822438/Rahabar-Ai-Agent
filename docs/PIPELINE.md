# Indexing and retrieval pipeline

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

**Shipped: 400/50**, giving 411 chunks and a storage amplification of 1.04 (71,398 stored words / 68,605 original).

Measured by retrieval only with the shipped heading fix and keyword boost, on the 15 answerable golden questions:

| Size (tokens) | Overlap (tokens) | recall@3 | recall@5 | Chunks stored | Storage amplification |
| --- | --- | --- | --- | --- | --- |
| 250 | 50 | 0.93 | 1.00 | 535 | 1.12 |
| 400 | 50 | 0.93 | 1.00 | 411 | 1.04 |
| 600 | 100 | 0.93 | 1.00 | 372 | 1.05 |

**The golden set does not separate these three on recall.** We chose 400/50 for two smaller reasons: the lowest storage amplification, and q12 ranks first where 250/50 ranks it second. With only 15 questions, that is weak evidence.

**The bigger change was the keyword boost.** At 400/50 before the boost and heading fix, recall@3 was 0.80, recall@5 was 0.87 and exact-term recall was 0 of 2. That earlier figure used the same questions before Prospectus alternatives were added, so part of the gain comes from the golden set change. q05's rank stays 5, so it misses at recall@3.

## Embedding
`nomic-embed-text` through Ollama on the host, with 768-dimensional vectors, using the `search_document:` and `search_query:` prefixes. The pin is one key, `EMBED_MODEL` in `k8s/base/configmap.yaml:10`, read by both the API and the indexer.

The indexer records `embed_model` and `dimension` in the collection metadata (`indexer/pipeline/store.py:42-48`). The API compares them on every `/readyz` call, returns 503 and logs the conflict on a mismatch (`api/app/routes/health.py:17-26`). Evidence: `docs/evidence/embed-pin-mismatch.txt`.

## Relevance floor: two layers
No single floor can separate these, at 400/50:

| Question | Should it answer? | Top score |
| --- | --- | --- |
| Off-topic, such as cooking or Python code (5 tried, plus one personal question) | No | 0.51 to 0.59 |
| Hostel room allotment (q14) | No | 0.62 |
| Bus route to campus (not in the golden set) | No | 0.70 |
| Clause 1.21 (q09) | Yes | 0.71 |
| Hostel fee (q13) | No | 0.74 |

The hostel fee question sits above an answerable one, because fee pages are genuinely close to it in meaning. A floor high enough to stop it would also block q09.

- **Layer 1, `RELEVANCE_FLOOR` = 0.65:** catches clearly irrelevant questions without calling the model. It sits between off-topic questions and the lowest answerable score, and also stops q14.
- **Layer 2, the model and code:** evidence that passes goes to the model, which sets `answered_from_context=false` when it doesn't answer the question. The citation check then drops anything not retrieved for this request.

Layer 2 depends on the model's judgement, so it can fail where a threshold could not. That is why the gate requires 100% must-abstain in the live eval. In the baseline run, q14 stopped at layer 1 and q13 at layer 2.

## Semantic cache
Measured with `eval/cache_threshold.py` on real embeddings: 5 repeated questions and 8 paraphrases that should hit, and 12 different-question pairs that must not:

| Threshold | Repeats (of 5) | Paraphrases (of 8) | False hits (of 12) |
| --- | --- | --- | --- |
| 0.85 | 5 | 8 | 4 |
| 0.90 | 5 | 8 | 2 |
| 0.92 | 5 | 8 | 1 |
| 0.93 | 5 | 8 | 0 |
| **0.94 (shipped)** | 5 | 7 | 0 |
| 0.95 | 5 | 6 | 0 |
| 0.96 | 5 | 5 | 0 |

**The false hit that ruled out 0.92:** "What minimum CGPA must an MS student maintain to avoid a warning?" against the same question for an undergraduate scores 0.923. The answers differ, 2.5 against 2.00. We first shipped 0.92 from a smaller set of 6 paraphrase and 7 different pairs, where a slightly different wording of this pair scored 0.919. That is why the re-check was needed: small rewording moved it across the line.

**Why 0.94 and not 0.93:** 0.93 also has zero false hits, but clears that pair by only 0.007. 0.94 clears it by 0.017. The cost is one missed paraphrase (0.938), which only means one extra model call, while a false hit gives a student the wrong rule. Repeated questions score at least 0.998, so they hit at any threshold here. The test set is still small, so re-run the script if the questions change. Re-indexing clears the cache (ADR 0002).

## Evaluation method
`eval/run_eval.py` sends each golden question through the Ingress. A retrieved chunk matches a golden passage when the source file is the same and one section name contains the other. A passage may list `alternatives`, other current documents stating the same rule, and finding any one counts. Citation validity checks each citation's source, section and page against that response's retrieved chunks.

Chunking and threshold tuning used retrieval or embeddings only, to save Gemini quota; only the final eval used Gemini, paced at 8 seconds between questions.

**Baseline (`eval/baseline.json`):** recall@3 0.93, recall@5 1.00, citation validity 1.00, must-abstain 100%.

**What these numbers do not show:**
- Gemini returned 503 twice for q12, so that run gave a canned fallback and it scored as not answered. The first run had the same outage on q05, where a repeat asked by hand answered correctly. We reran once with a clean cache and kept that run, and report the fallback rather than hide it.
- q02 answered "six years", which is correct, but `expect` looks for "6 years". `expect` is not part of the gate.
- Scores of 1.00 on 15 questions are small-sample results, and part of this golden set shaped the boost and the section mapping.
- Section names were matched to the index after the questions were written; the questions and answers were not changed to fit retrieval.
