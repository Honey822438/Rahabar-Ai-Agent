"""The real retriever: reads Chroma, never writes it (sections 3.2 and 4.4)."""

from __future__ import annotations

import re
from typing import Any

import httpx

from ..config import Settings
from ..schemas import Passage

EMBED_TIMEOUT_SECONDS = 30.0
# nomic-embed-text is trained with task prefixes. The indexer uses "search_document: ".
QUERY_PREFIX = "search_query: "

_DOCUMENT_WORD = r"(?:rules?|regulations?|handbook|policy|policies|edition|version|prospectus)"
_ASKS_FOR_OLDER = re.compile(
    rf"\b(?:older|previous|earlier|former|outdated|superseded|old)\s+(?:\w+\s+)?{_DOCUMENT_WORD}\b"
    rf"|\b20(?:[01]\d|2[0-5])\s+(?:\w+\s+)?{_DOCUMENT_WORD}\b"
    rf"|\b{_DOCUMENT_WORD}\s+(?:\w+\s+)?(?:of|from|in|before)\s+20(?:[01]\d|2[0-5])\b",
    re.IGNORECASE,
)


def asks_for_older_version(question: str) -> bool:
    """True only when the question explicitly names an older document version."""
    return bool(_ASKS_FOR_OLDER.search(question))


class ChromaRetriever:
    name = "chroma"

    def __init__(self, settings: Settings) -> None:
        import chromadb  # the thin client, from chromadb-client in requirements.txt
        from chromadb.config import Settings as ChromaSettings

        self.settings = settings
        self.client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port,
                                          settings=ChromaSettings(anonymized_telemetry=False))

    def _embed_query(self, question: str) -> list[float]:
        prefix = QUERY_PREFIX if self.settings.embed_model.startswith("nomic") else ""
        response = httpx.post(
            f"{self.settings.ollama_url}/api/embed",
            json={"model": self.settings.embed_model, "input": [prefix + question]},
            timeout=EMBED_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return list(response.json()["embeddings"][0])

    def retrieve(self, question: str, k: int) -> list[Passage]:
        vector = self._embed_query(question)
        # Looked up on every request: the indexer replaces the collection when it re-indexes.
        collection: Any = self.client.get_collection(self.settings.collection)
        where = None if asks_for_older_version(question) else {"superseded": False}
        found = collection.query(query_embeddings=[vector], n_results=k, where=where,
                                 include=["documents", "metadatas", "distances"])
        return [
            Passage(
                chunk_id=chunk_id,
                text=text,
                source=str(meta["source"]),
                section=str(meta["section"]),
                page=int(meta["page"]),
                score=1 - distance,  # cosine distance to similarity
            )
            for chunk_id, text, meta, distance in zip(
                found["ids"][0], found["documents"][0], found["metadatas"][0],
                found["distances"][0], strict=True,
            )
        ]
