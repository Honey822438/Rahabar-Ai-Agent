# C1 + C2: chunk-size change and release gate

One change only: chunk size/overlap (words). Each candidate is synced from the same lake into its own
collection (`scripts/build_collection.py`). Same extractor, embedder (nomic-embed-text), top_k 5,
floor 0.65 and prompt. Suite runs are seeded (42), at temperature 0, with `INJECTION_RAIL=off` (the
same code path as the baseline).

| run | collection | chunks | recall@5 | MRR | nDCG@5 | abstain (unans.) | faithful | correct | p50 s | p95 s | retr. p95 ms | gate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline 400/50 | rahbar | 430 | 0.962 | 0.866 | 0.810 | 1.0 | 1.0 | 0.88 | 2.28 | 13.5 | 132 | - |
| c600 600/100 | rahbar_c600 | 391 | 0.962 | 0.867 | 0.775 | 1.0 | 1.0 | 0.92 | 2.29 | 16.6 | 288 | **PASS** (10/10), exit 0 |
| c100 100/0 | rahbar_c100 | 1009 | 0.962 | 0.929 | 0.793 | 1.0 | 1.0 | 0.92 | 1.88 | 27.6 | 254 | **FAIL** (9/10: p95 latency), exit 1 |

Files: `*-candidate-c600.json`, `*-candidate-c100-bad.json`, `gate-candidate-*.md`, `c1-compare-*.md`.

## Honest reading
- **c600 passes.** Retrieval is unchanged at recall@5 and MRR. nDCG@5 drops 0.035, within the 0.05
  tolerance: bigger chunks pull in fewer distinct relevant chunks below rank 1. Answers are as good.
  Retrieval p95 doubles (larger documents) but stays under 400 ms.
- **c100 fails the gate, but on latency only, and that latency comes from the provider, not the
  chunking.** Its p50 is the fastest of the three. p95 is high because 12/31 questions needed a
  retry after Gemini free-tier 429/503 (the baseline needed 7). Its quality did not get worse:
  100-word chunks fit this corpus's short numbered clauses well (MRR rises to 0.93). So "100/0" is
  not a deliberately bad candidate on this golden set. The gate stopped it, but for the wrong
  reason, and a quieter Gemini minute could let it pass.
- Lesson for the gate: e2e p95 measured on a free hosted LLM is noisy. A latency rule should use
  our own stages (retrieval p95), or e2e latency measured without provider retries.
  Follow-up: a degradation the gate catches on QUALITY (see PLAN-A3 progress notes).
