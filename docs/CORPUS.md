# Corpus

Source: FAST-NUCES public website · Documents: 9 (7 PDFs, 2 HTML pages) · Pages: 279 PDF pages plus the 2 web pages

Exact files, versions and SHA-256 hashes are in `corpus/MANIFEST.md`. Check them with `python corpus/fetch.py --verify`.

| # | Required property | Document(s) that provide it | Evidence or notes |
| --- | --- | --- | --- |
| 1 | At least 6 documents, 40 pages | All 9 in `corpus/sources.yaml` | PDF page counts from `pdfinfo`: 26, 58, 5, 64, 33, 85, 8 = 279 |
| 2 | Two versions of one policy | Undergraduate Academic Rules (Aug 2023) and Academic Rules Handbook (Jun 2026) | The 2026 handbook supersedes 2023. `superseded: true` and `doc_version: "2023-08"` in `corpus/sources.yaml` become chunk metadata; retrieval excludes superseded chunks unless a question asks for an older version |
| 3 | Scanned, image-only PDF | Faculty Entrepreneurship and Technical Start-ups Policy | `pdffonts` lists no fonts and `pdftotext` returns no text across all 8 pages; the indexer logged `ocr_pages: 8`. The 2023 rules are also nearly all scans (24 of 26 pages needed OCR) |
| 4 | A table with real information | Fee Structure page, Grading page, annual reports | Fees are kept as rows, such as `Campus Transfer Fee \| Rs. 5,000` |
| 5 | Long definitions | Student Handbook (Jun 2026) | Cheating, plagiarism and harassment are defined over several clauses on pages 12 to 14 |
| 6 | A deliberately absent topic | Hostel and transport rules: the prospectus document "Transport and Hostel Facilities" was left out | Students plausibly ask about hostel fees, allotment or rules. See the note below |
| 7 | Exact-term content | Academic Rules Handbook (Jun 2026), Fee Structure page | Clause 1.21 (attendance), clause 5.4 (minimum CGPA of 2.00 to avoid academic warning), and fee amounts |

## Note on the absent topic
"Absent" means no hostel rules, fees or allotment process. The word itself is not absent: the two annual reports and the Student Handbook mention that hostels exist (7 lines across them). This explains why hostel questions score above unrelated ones in retrieval.

So must-abstain questions should ask about things the corpus really lacks, such as hostel fees, and not "does the university have a hostel?", which it can answer. The system must abstain on these even though similar words are retrieved.

## Overlapping current documents
The Prospectus 2026 rules and the 2026 handbook cover the same rules with different clause numbers, and both are current. A citation to either can be correct.
