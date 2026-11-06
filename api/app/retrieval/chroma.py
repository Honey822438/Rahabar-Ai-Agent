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

OLDER = "older"
# How many extra hits to fetch when post-filtering by year, as Chroma has no prefix match.
YEAR_OVERFETCH = 4

_DOCUMENT_WORD = r"(?:rules?|regulations?|handbook|policy|policies|edition|version|prospectus)"
_OLDER_YEAR = r"20(?:[01]\d|2[0-5])"
_NAMES_YEAR = re.compile(
    rf"\b(?P<a>{_OLDER_YEAR})\s+(?:\w+\s+)?{_DOCUMENT_WORD}\b"
    rf"|\b{_DOCUMENT_WORD}\s+(?:\w+\s+)?(?:of|from|in|before)\s+(?P<b>{_OLDER_YEAR})\b",
    re.IGNORECASE,
)
_NAMES_OLDER = re.compile(
    rf"\b(?:older|previous|earlier|former|outdated|superseded|old)\s+(?:\w+\s+)?{_DOCUMENT_WORD}\b",
    re.IGNORECASE,
)


def requested_version(question: str) -> str | None:
    """An older year the question names, OLDER if it asks for "the old policy", else None."""
    named = _NAMES_YEAR.search(question)
    if named:
        return named.group("a") or named.group("b")
    return OLDER if _NAMES_OLDER.search(question) else None


def asks_for_older_version(question: str) -> bool:
    """True only when the question explicitly names an older document version."""
    return requested_version(question) is not None


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
        version = requested_version(question)
        # An older-version question reads only superseded documents, so a current document
        # can't out-rank the one that was asked for.
        where = {"superseded": version is not None}
        limit = k * YEAR_OVERFETCH if version not in (None, OLDER) else k
        found = collection.query(query_embeddings=[vector], n_results=limit, where=where,
                                 include=["documents", "metadatas", "distances"])
        passages = self._to_passages(found, version)
        return passages[:k]

    @staticmethod
    def _to_passages(found: Any, version: str | None) -> list[Passage]:
        year = version if version not in (None, OLDER) else None
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
            # No document from that year means an empty result, so the service abstains
            # instead of quoting a different version.
            if year is None or str(meta["doc_version"]).startswith(year)
        ]
