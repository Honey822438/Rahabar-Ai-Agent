# ADR 0004: Hosted LLM on a free tier, and what that means for student data

## Status
Accepted · 6 Nov 2026

## Context
The laptop has 14 GB of RAM and no GPU, and minikube gets 6 GB. A local model would be slow and compete with the cluster. The project has no budget. But any hosted free tier means student questions leave the cluster.

## Decision
`LLM_PROVIDER=hosted` calls Google Gemini (`gemini-flash-lite-latest`) through its OpenAI-compatible endpoint (`api/app/providers/llm/hosted.py`). If `GROQ_API_KEY` exists in the Secret, Groq models are tried after a rate limit or outage (`hosted.py:23,42-47`). `ollama-host` remains available as a secondary mode. Embeddings always stay on our own host through Ollama.

Keys exist only in the `rahbar-secret` Secret, created by command. They are never committed or logged. The API's egress allows HTTPS to non-private addresses only (`k8s/base/networkpolicy.yaml:105-111`).

## Data governance
**What leaves the cluster:** the student's question and the retrieved corpus passages go to Google, or to Groq on failover. Corpus passages are public documents. Questions may not be, because a student could type a name, roll number or a personal situation.

**What the free tier means:** Google's terms for unpaid Gemini API services allow submitted content to be used to improve its products, and people may review it. They tell users not to submit sensitive or personal information. We therefore treat free-tier prompts as not private. Check the current terms at <https://ai.google.dev/gemini-api/terms> before relying on this.

**What we keep:** Redis stores recent questions and answers (`api/app/services/cache.py:87-92`, last 1000) plus cached answers for up to 14 days. Our request log line records chunk ids and scores, not the question (`api/app/services/answer.py:123`).

**Not done yet:** we do not filter personal data out of questions, and the UI does not warn users. This is acceptable for coursework on public documents, but not for a real student deployment.

**For a real deployment:** move to a paid tier with a no-training agreement, or a university-hosted model; add a UI notice and personal-data redaction; and agree a retention period for stored turns.

## Options considered
- **Local generation only.** The best privacy, but too slow on this CPU and memory budget for an interactive service or a full evaluation.
- **Paid API.** Better terms, but costs money the project does not have.

## Consequences
- Free-tier rate limits are low, so the eval is paced, and the cache and Groq failover matter more.
- Provider outages produce a canned fallback, never a 500 (`answer.py:21-32`).
- The model alias `gemini-flash-lite-latest` can change underneath us. The golden-set gate is how we would notice a quality drop.
