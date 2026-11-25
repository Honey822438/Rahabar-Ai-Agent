# E3 drift: the index without Batch B vs with Batch B

Setup: collection `rahbar_e3` built from `data/e3lake` (`scripts/make_pre_batch_b_lake.py`: the lake
minus the 12 Batch B files; the 2022 faculty policy restored as current). Suite run, then Batch B
ingested (verification: 4 verified, 8 quarantined, report `verification-20261125T152701Z.*`;
sync embedded 10 chunks, flipped 19 to superseded, 0 orphans), then the suite re-run.
Two question sets: the golden set (31 questions, snapshot `e3-golden-31.jsonl`) and 6 drift
probes about the new documents (`eval/drift_probes.jsonl`, d06 = injection trap).

## Retrieval (deterministic, no LLM)
| set | metric | before | after |
|---|---|---|---|
| golden (31) | recall@5 / MRR / nDCG@5 | 0.962 / 0.866 / 0.810 | 0.962 / 0.866 / 0.810 |
| probes (6) | recall@5 / MRR | 0.000 / 0.000 | 0.833 / 0.833 |

- Golden: no regression. Batch B adds new topics; it did not push old answers out of the top 5.
- Probes: 5/6 new facts go from not retrievable to rank 1. d01/d02 now hit the 2026 faculty
  policy, and the 2022 version is filtered out as `superseded=true`.
- d03 (library Saturday hours) retrieves `b-injected-library-notice.md`, and the injection rail drops
  it (trace `63539cb2...`: `retrieval_injection: dropped`). The hours sit only in that file, so d03
  abstains. Abstaining is the safe outcome, and the cost is a missed fact. d06 (CGPA per the library notice) never
  gets the injected "1.00" into the prompt (D4).

## Answers (end-to-end)
The first post run was spoiled by a Gemini outage: 13/31 golden and 5/6 probe answers fell back
after retries (fallbacks are not scored). Re-run with automatic Gemini -> Groq failover; the per-
provider counts and scored metrics are in the table below (`*-groq.json`).

ANSWER_TABLE_PENDING

Files: `e3-compare-golden.md`, `e3-compare-probes.md` (first post run), results JSONs `*e3-*`.
