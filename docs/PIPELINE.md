# Indexing and retrieval pipeline

<!-- STARTER-TODO(3.1, 3.3, 5.2): fill each section with your numbers, then delete this comment. -->

## Extraction
Which documents needed OCR, one before-and-after example of a table, what could not be recovered.

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
The rules you applied, and one thing you deliberately did not strip.

## Chunking
Size and overlap you shipped, storage amplification (stored tokens / original tokens),
and the three configurations you measured:

| Size (tokens) | Overlap (tokens) | recall@5 | Chunks stored |
| --- | --- | --- | --- |

## Embedding
Model, vector dimension, where the pin lives, how the API checks it.

## Semantic cache
Thresholds you tried, the false hit that ruled one out, the one you shipped.

## Evaluation method
How recall@k matches retrieved passages to golden ones (by source and section? by chunk id?).
