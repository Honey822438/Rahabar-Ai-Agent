# ADR 0002: Redis stores the semantic cache

## Status
Accepted · 6 Nov 2026. The threshold is chosen separately from golden-set measurements.

## Context
Generation is the slow step, and our Gemini free tier allows few requests per minute. Students also ask the same things in slightly different words. All 3 API replicas must share one cache, and it must survive pod restarts. A cached mistake reaches everyone, and answers from an old index must never be served.

## Decision
A Redis Deployment with a PVC (`k8s/base/redis.yaml`), reachable only from the API by NetworkPolicy. A hit is cosine similarity at or above `CACHE_THRESHOLD` from the ConfigMap, compared against stored question vectors (`api/app/services/cache.py:69-77`).

- **Not cached:** follow-ups and older-version questions (`cache.py:42-44`), abstentions and fallbacks (`api/app/services/answer.py:120`).
- **Invalidation:** entries are stored under the `index_generation` the indexer writes to the collection metadata (`indexer/pipeline/store.py:46`). When the API sees a new generation it deletes the old entries (`cache.py:59-67`). The indexer cannot reach Redis, because the NetworkPolicy allows only the API. This meets "flush on re-index" without opening another path.
- **Failure:** if Redis fails during a request, that request runs without the cache (`answer.py:48`). `/readyz` still reports Redis as a failure.
- `AskResponse` gains a `cached` field beyond the starter contract (`api/app/schemas.py:65`), so clients, logs and tests can see a hit directly.

## Options considered
- **A second Chroma collection.** It has vector search built in, but the API would then write to Chroma, breaking the rule from ADR 0001 that only the indexer writes. Expiry and bulk deletion are also awkward.
- **Memory inside each API pod.** Hit rates split across replicas and everything is lost on restart.
- **Exact-match Redis keys.** Safe, but misses reworded questions, which are the main reason to cache.

## Consequences
- Lookup scans every entry in the current generation in Python, which costs O(n) per request. This is fine for a small cache; a much larger one would need a real vector index.
- Each lookup still embeds the question, so Ollama must be up even for a hit.
- Invalidation is lazy: old entries go on the first request after a re-index, not when the Job ends.
- Too low a threshold serves the wrong answer to a similar question, so it needs measuring.
