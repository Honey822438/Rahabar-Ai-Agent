"""The semantic cache in Redis (section 3.3).

Entries live under the index generation the indexer recorded, so answers from an old index can
never be served. Only the API may reach Redis, so the API does the invalidation: it deletes old
generations when it sees a new one. A Redis failure disables the cache for that request, nothing
more.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from typing import Any

from ..config import Settings
from ..retrieval.chroma import requested_version
from ..schemas import AskResponse

log = logging.getLogger("rahbar.cache")

PREFIX = "rahbar:cache:"
GENERATION_KEY = "rahbar:generation"
TURNS_KEY = "rahbar:turns"
MAX_TURNS = 1000
ENTRY_TTL_SECONDS = 14 * 24 * 3600
_FOLLOW_UP = re.compile(
    r"^\s*(?:and|but|also|so|then|what about|how about|why (?:is|was) that|what else)\b"
    r"|\b(?:it|that|this|those|these|they|them|above|previous answer|you said)\b"
    r"(?=[^a-z]*$)",
    re.IGNORECASE,
)


def is_followup(question: str) -> bool:
    """True if the question leans on an earlier turn, so its answer can't be shared."""
    return bool(_FOLLOW_UP.search(question))


def skip_cache(question: str) -> bool:
    """Follow-ups depend on context, and older-version questions sit close to current ones."""
    return is_followup(question) or requested_version(question) is not None


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b)) / norm if norm else 0.0


class SemanticCache:
    def __init__(self, client: Any, threshold: float) -> None:
        self.client = client
        self.threshold = threshold

    def invalidate_if_reindexed(self, generation: str) -> None:
        """Flush every other generation's entries when the index has changed."""
        if self.client.get(GENERATION_KEY) == generation:
            return
        for key in self.client.scan_iter(match=f"{PREFIX}*"):
            if key != PREFIX + generation:
                self.client.delete(key)
        self.client.set(GENERATION_KEY, generation)
        log.info("cache invalidated after a re-index", extra={"generation": generation})

    def lookup(self, generation: str, vector: list[float]) -> AskResponse | None:
        """The closest entry at or above the threshold."""
        best, best_score = None, self.threshold
        for raw in self.client.hvals(PREFIX + generation):
            entry = json.loads(raw)
            score = cosine(vector, entry["vector"])
            if score >= best_score:
                best, best_score = entry["response"], score
        return AskResponse.model_validate(best) if best else None

    def store(self, generation: str, question: str, vector: list[float],
              response: AskResponse) -> None:
        key = PREFIX + generation
        field = hashlib.sha256(question.encode()).hexdigest()
        entry = {"vector": vector, "response": response.model_dump()}
        self.client.hset(key, field, json.dumps(entry))
        self.client.expire(key, ENTRY_TTL_SECONDS)

    def store_turn(self, question: str, response: AskResponse) -> None:
        turn = {"request_id": response.request_id, "question": question,
                "answer": response.answer, "cached": response.cached,
                "answered_from_context": response.answered_from_context}
        self.client.lpush(TURNS_KEY, json.dumps(turn))
        self.client.ltrim(TURNS_KEY, 0, MAX_TURNS - 1)

    def ping(self) -> bool:
        return bool(self.client.ping())


def get_cache(settings: Settings) -> SemanticCache | None:
    if not settings.redis_host:
        return None
    import redis

    client = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True,
                         socket_timeout=1, socket_connect_timeout=1)
    return SemanticCache(client, settings.cache_threshold)

