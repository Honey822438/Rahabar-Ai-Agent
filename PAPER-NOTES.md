# RAGOps paper: notes for Assignment 03

*Xu, Weytjens, Zhang, Lu, Weber, Zhu. "RAGOps: Operating and Managing RAG Pipelines" (preprint, 2026).* Only the parts the assignment uses, in plain words.

## The one idea (Figure 3)
A RAG system has **two lifecycles that run side by side**:
1. **Query processing pipeline** (top row): normal DevOps. **a. Plan → b. Build → c. Test → d. Release → e. Deploy → f. Operate & Monitor → g. Analyze & Feedback**, then back to Plan.
2. **Data management** (bottom row): **1. Ingest → 2. Verify → 3. Update data lake → 4. Update retrieval sources → 5. Offline testing**, with **6. Live testing** and **7. Check coverage** linking back to the top row.

Data changes much more often than code, so data gets its **own lifecycle** and its **own tests**.

## 3.2 Process view
- **Query pipeline:** (optional query rewrite) → retriever decides how to search → embed query → vector search → **rerank** → generator builds the prompt → LLM → **validate the response** → user.
- **Data management:** chunk → embed → store in the vector DB, kept current by Section 4.2.
- **3.2.3 Guardrails**, at four places:
  - **Input rails (I):** check or reject user input
  - **Dialog rails (D):** shape the prompt and the conversation
  - **Retrieval rails (R):** drop or modify retrieved chunks (e.g. **poisoned / injected text**)
  - **Output rails (O):** reject or clean the answer

  → Our injection defence is a **retrieval rail**, and D4 wants its action written to the trace.

## 4.2 Data management (Part A)
- **4.2.1 Ingest:** pull data from files, APIs, crawlers and so on, including **updates and deletions**, plus format conversion (PDF → text).
- **4.2.2 Verify:** the paper's checks:
  - **Quality:** not corrupted or malformed
  - **Completeness:** all metadata present (timestamp, author, source), text not truncated
  - **Recency:** old versions **archived and replaced**, not kept live
  - **Consistency:** contradictions detected by semantic similarity (*the assignment does not require this one*)
  - **Uniqueness:** exact duplicates by **hash**, semantic duplicates by **embeddings**
- **4.2.3 Update data lake:** store verified data as a single source of truth. **Archive old versions instead of deleting them** (rollback + history). **Version every change.** Keep the data **free of orphans**.
- **4.2.4 Update retrieval sources:** **incremental** chunking and embedding of only new or changed data. Deletions and outdated data are removed from the index.

## 4.2.5 Offline testing (Part B) and Table 1
Triggered by **pipeline changes** (new LLM, chunking, embedding) or **data shifts** (new sources). **Three levels:**

| Level | What | Traditional metric | RAG metric |
|---|---|---|---|
| **Module** (embedding) | similarity, drift, efficiency | embedding time, memory | cosine similarity, embedding drift |
| **Component** (retrieval) | rank relevance, **resilience to noise** | retrieval latency, index update speed | **MRR, recall@K, precision@K, nDCG** |
| **End-to-end** (answers) | faithfulness, hallucination, correctness | full pipeline latency | **faithfulness**, hallucination rate |

- Test sets must be **domain-specific** and expanded **before** adding new domains (forward adaptability), with old tests kept (backward compatibility). Synthetic data covers edge cases.
- **Stochasticity:** approximate search, tie-breaking and LLM sampling vary between runs → **fix random seeds**.

## 4.2.6 Live testing (Part C3 / F3)
Release safely with **shadow testing**, **A/B testing** or a **staged roll-out**. Set **predefined thresholds**; crossing one sends the system **back to offline testing**. → Our **release gate + second Deployment + rolling update / undo**.

## 4.2.7 Coverage checking (Part E)
Are the **test questions still representative of real user questions?**
- **Query coverage:** compare live queries with test queries using **embedding cosine similarity** (or TF-IDF). Low scores or new clusters mean gaps.
- Also retrieval, generation and vocabulary coverage (TF-IDF for new terms).
- **Example threshold:** *if less than 85% of live queries reach a certain similarity to the test queries, expand the test set.*

## 5.1 Qualities and Table 2 (report table 2)
| Quality | Paper's design considerations | → What we show |
|---|---|---|
| **Adaptability** | data structure construction, granularity configuration | chunk size / top_k in the ConfigMap; candidate collection; incremental updates |
| **Monitorability** | degradation detection (accuracy, latency, relevance), data source change detection, clear metrics | eval suite + gate thresholds, verification report, coverage script |
| **Observability** | retrieval: **injection detection**, relevance; generation: context adherence, toxicity, usefulness | trace JSONL, metrics summary, guardrail actions, faithfulness |
| **Traceability** | **versioning**, retrieval routing, **grounded source** | doc_version, collection + embedding version in the trace, trace tool rebuilds the prompt, citations |
| **Reliability** | resource usage, bandwidth | requests/limits from `kubectl top`, 3 replicas, HPA, rollout with maxUnavailable 0, p95 latency |

## 6.2 Lack of standard metrics (useful for report answer (d))
There's no standard set of metrics for RAG, so it's hard to judge components and the whole system. Early choices (chunking, embedding model) affect later stages, and their impact is hard to measure. → Argues for our **three-level suite** and for being careful with metrics like an LLM-judged faithfulness score.
