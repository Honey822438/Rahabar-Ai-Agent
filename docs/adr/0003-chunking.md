# ADR 0003: Structure-aware chunking with overlap

## Status
Accepted for the method · 6 Nov 2026. The final size and overlap depend on the three measured configurations in `docs/PIPELINE.md`, and 400/50 is provisional until then.

## Context
Answers must cite a source, section and page, so a chunk has to carry those. The corpus mixes numbered clauses, long definitions, tables and OCR text. Fixed-size splitting would cut clauses and table rows in half, and lose which heading they belonged to.

## Decision
`indexer/pipeline/chunk.py` splits by section, then paragraph, then sentence, under a target size, and repeats an overlap between neighbouring chunks. Each chunk keeps its source, section, page, version and `superseded` flag. `CHUNK_SIZE` and `CHUNK_OVERLAP` come from the ConfigMap (`k8s/base/configmap.yaml:18-19`), so trying a setting needs a re-index, not an image rebuild.

Size is counted in whitespace-separated words, as a simple stand-in for tokens. At 400/50 the corpus gives 372 chunks and a storage amplification of 1.05 (72,054 stored words from 68,604).

## Options considered
- **Fixed-size windows.** Simplest, but they ignore structure and damage citations.
- **Semantic splitting with embeddings.** It costs extra embedding calls on a CPU, with no evidence yet that we need it.
- **A real tokenizer.** More exact, but it adds a dependency and the embedding model's exact limit is not what we are tuning against.

## Consequences
- A section heading stays attached to text, which helps citations and exact-term search.
- Heading detection is heuristic (`chunk.py:33`), so OCR noise can produce wrong section names.
- A word count is only an estimate of the true token count, so stated sizes are approximate.
- Changing either value requires a re-index, which also clears the cache (ADR 0002).
