# C1 + C2: chunk-size change and release gate

One change only: chunk size/overlap (words). Each candidate is synced from the same lake into its own
collection (`scripts/build_collection.py`). Same extractor, embedder (nomic-embed-text), top_k 5,
floor 0.65 and prompt. Suite runs are seeded (42), at temperature 0, with `INJECTION_RAIL=off` (the
same code path as the baseline).

| run | collection | chunks | recall@5 | MRR | nDCG@5 | abstain (unans.) | faithful | correct | p50 s | p95 s | retr. p95 ms | gate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline 400/50 | rahbar | 430 | 0.962 | 0.866 | 0.810 | 1.0 | 1.0 | 0.88 | 2.28 | 13.5 | 132 | - |
| c600 600/100 | rahbar_c600 | 391 | 0.962 | 0.867 | 0.775 | 1.0 | 1.0 | 0.92 | 2.29 | 16.6 | 288 | **PASS** (10/10), exit 0 |
| c600 + top_k=1 | rahbar_c600 | 391 | 0.808 | 0.808 | 0.808 | 1.0 | 1.0 | 0.73 | - | 12.2 | 113 | **FAIL** (4 quality rules), exit 1 |
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

## Quality-failing candidate: top_k = 1 (config change, no rebuild)
`TOP_K=1 python eval/run_suite.py --collection rahbar_c600 --label candidate-c600-topk1-bad`.
The gate fails on **quality**: recall@5 0.96 -> 0.81 and MRR 0.87 -> 0.81 (a relevant chunk at rank 2+
never reaches the model), false abstentions 0.04 -> 0.32, correct answers 0.88 -> 0.73. Latency
passes (clean p95 5.2 s). Faithfulness stays 1.0, so the model stays grounded and abstains instead
of guessing. That is the right failure mode, but too many questions go unanswered to ship.
(The component level counts a chunk ranked below top_k as a miss when top_k < 5.)

## Gate change after c100: latency judged without provider outages
`config/gate.yaml` now ENFORCES `e2e.latency_p95_clean_s` (p95 over answers that needed no provider
retry/failover) and REPORTS `e2e.latency_p95_s` (all calls) without enforcing it. The c600 and c100
gate reports above were produced with the earlier rule set (all-calls p95 enforced) and are kept as
they were. Those two runs predate the clean metric.
