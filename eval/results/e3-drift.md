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

| set | metric | before (Gemini) | after (Groq failover) |
|---|---|---|---|
| golden (31) | answered by | gemini 31 | groq 30, no LLM call 1 (Gemini 429 on all 30) |
| golden (31) | abstention on must-abstain | 1.00 | 1.00 |
| golden (31) | false abstention | 0.038 | 0.038 |
| golden (31) | answer contains expected fact | 0.885 | 0.769 |
| golden (31) | faithfulness (judge) | 1.00 (25 judged) | 0.917 (24 judged) |
| golden (31) | citation validity | 1.00 | 1.00 |
| probes (6) | answered by | gemini 4, fallback 2 | groq 5, no LLM call 1 |
| probes (6) | expected new fact in answer | 0/2 scored | 3/6 (d01 three years, d02, d04 December) |

Reading:
- The probes show Batch B working end to end. The new 2026 faculty policy answers d01/d02, and the sports
  week date (d04) is now answered. d05 names the right fair date ("15 January 2027"), but Groq wrote
  it with narrow no-break spaces (U+202F), so the plain substring "15 January" did not match. This is a scoring
  artefact, not a model error. Follow-up: normalise Unicode spaces in the expect check.
  d03 abstains because the injection rail dropped its only source. d06 abstains correctly, and "1.00" never appears.
- On the golden set, retrieval is identical, but expected-fact and faithfulness drop. **That is the provider change
  (Groq gpt-oss-20b instead of Gemini), not Batch B.** The prompts, retrieved chunks and
  citations are the same, and only the generator differs. A clean drift attribution would need the same
  model on both sides. This is resolved by the Groq-vs-Groq comparison below.
- **Fair comparison, same generator (Groq vs Groq):** the pre-Batch-B index was rebuilt as
  `rahbar_e3pre` (10 docs, 420 chunks, OCR cache reused) and the 31 golden questions were re-run with Groq.

  | golden (31), Groq on both sides | before Batch B | after Batch B |
  |---|---|---|
  | recall@5 / MRR | 0.962 / 0.866 | 0.962 / 0.866 |
  | abstention on must-abstain / false abstention | 1.00 / 0.038 | 1.00 / 0.038 |
  | answer contains expected fact | 0.769 | 0.769 |
  | faithfulness (judge) | 0.960 | 0.917 |
  | citation validity | 1.00 | 1.00 |

  With the generator held constant, Batch B causes **no regression** on the golden set. The expected-fact rate is
  identical. The only per-question flips are h01 (now found) and h05 (now missed), both with different wording from the
  same chunks. The faithfulness change (-0.04) is about one judged answer out of roughly 24, which is within run-to-run variation (B4).
  Conclusion: the earlier 0.885 -> 0.769 drop was caused by the change of LLM (Gemini -> Groq), not by the data.
  Files: `*-e3-pre-batch-b-groq.json`, `e3-compare-golden-groq-vs-groq.md`.
- Provider counts come from the traces (`llm.answered_by`, `failed_over_from`). Gemini returned
  429 on every call in both reruns (daily free quota exhausted), so Groq answered every LLM call.


Files: `e3-compare-*-groq.md` (Groq reruns), `e3-compare-golden.md`, `e3-compare-probes.md` (first post run, outage), results JSONs `*e3-*`.
