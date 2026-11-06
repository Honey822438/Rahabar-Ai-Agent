"""Stage 4: Embed. One vector per chunk, from the pinned model only."""

from __future__ import annotations

import httpx

from .config import IndexerSettings

BATCH_SIZE = 32
TIMEOUT_SECONDS = 300.0
# nomic-embed-text is trained with task prefixes. The API must use "search_query: ".
DOCUMENT_PREFIX = "search_document: "


def embed(texts: list[str], settings: IndexerSettings) -> list[list[float]]:
    """Embed with settings.embed_model and nothing else, in batches."""
    prefix = DOCUMENT_PREFIX if settings.embed_model.startswith("nomic") else ""
    vectors: list[list[float]] = []
    with httpx.Client(base_url=settings.ollama_url, timeout=TIMEOUT_SECONDS) as client:
        for start in range(0, len(texts), BATCH_SIZE):
            batch = [prefix + text for text in texts[start:start + BATCH_SIZE]]
            response = client.post("/api/embed",
                                   json={"model": settings.embed_model, "input": batch})
            response.raise_for_status()
            found = response.json()["embeddings"]
            if len(found) != len(batch):
                raise RuntimeError(f"asked for {len(batch)} embeddings, got {len(found)}")
            vectors.extend(found)
    return vectors
