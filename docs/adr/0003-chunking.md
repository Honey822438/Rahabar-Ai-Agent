# ADR 0003: Structure-aware chunking with overlap

## Status
Accepted · 7 Nov 2026. Measurements are in `docs/PIPELINE.md`.

## Context
Answers must cite a source, section and page, so a chunk has to carry those. The corpus mixes numbered clauses, long definitions, tables and OCR text. Fixed-size splitting would cut clauses and table rows in half, and lose which heading they belonged to.

## Decision
`indexer/pipeline/chunk.py` splits by section, then paragraph, then sentence, under a target size, and repeats an overlap between neighbouring chunks. Each chunk keeps its source, section, page, version and `superseded` flag. `CHUNK_SIZE` and `CHUNK_OVERLAP` come from the ConfigMap (`k8s/base/configmap.yaml:18-19`), so trying a setting needs a re-index, not an image rebuild.

Size is counted in whitespace-separated words, as a simple stand-in for tokens. We ship 400/50, which gives 411 chunks and a storage amplification of 1.04 (71,398 stored words from 68,605).

250/50, 400/50 and 600/100 all scored recall@3 0.93 and recall@5 1.00 on our 15 answerable questions, so recall did not decide this. We chose 400/50 for its lowest amplification and because q12 ranks first where 250/50 ranks it second.

## Related decisions from the same measurements
**Keyword boost.** Chunking did not fix exact terms; before the boost, clause questions scored 0 of 2. Chunks containing a clause number or course code are now placed first (`api/app/retrieval/chroma.py`), keeping their true scores.

**Numbered headings.** A heading such as "5. Unacceptable Uses of Generative AI Tools" was being joined to the next line, so its text was filed under "2. Objectives". The cleaner now keeps numbered headings separate (`indexer/pipeline/clean.py`).

**Two-layer abstention.** No single relevance floor works: the hostel fee question (must abstain) scores 0.74, above clause 1.21 (must answer) at 0.71. So `RELEVANCE_FLOOR` = 0.65 only removes clearly irrelevant questions, and the model's `answered_from_context=false` plus the citation check handle in-domain gaps. This relies on the model, so the eval gate requires must-abstain at 100%.

## Options considered
- **Fixed-size windows.** Simplest, but they ignore structure and damage citations.
- **Semantic splitting with embeddings.** It costs extra embedding calls on a CPU, with no evidence yet that we need it.
- **A real tokenizer.** More exact, but it adds a dependency and the embedding model's exact limit is not what we are tuning against.

## Consequences
- A section heading stays attached to text, which helps citations and exact-term search.
- Our golden set is too small to separate these sizes, so the choice could change with more questions.
- Heading detection is heuristic (`chunk.py:33`), so OCR noise can produce wrong section names.
- A word count is only an estimate of the true token count, so stated sizes are approximate.
- Changing either value requires a re-index, which also clears the cache (ADR 0002).
