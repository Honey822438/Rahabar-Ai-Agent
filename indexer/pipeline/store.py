"""Stage 5: Store. The only code in the whole system that writes to Chroma.

A new index is built in a temporary collection and verified, and only then replaces the
live one. A Job that fails halfway leaves the working index untouched.
"""

from __future__ import annotations

import time
from typing import Any

from .config import IndexerSettings
from .models import Chunk

BATCH_SIZE = 500
BUILD_SUFFIX = "__build"


def get_client(settings: IndexerSettings) -> Any:
    import chromadb  # the thin client, from chromadb-client in requirements.txt
    from chromadb.config import Settings as ChromaSettings

    return chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port,
                               settings=ChromaSettings(anonymized_telemetry=False))


def _delete_if_present(client: Any, name: str) -> None:
    try:
        client.delete_collection(name)
    except Exception:  # Chroma raises different errors by version when it does not exist
        pass


def store(chunks: list[Chunk], vectors: list[list[float]], settings: IndexerSettings) -> int:
    """Write every chunk with its vector and metadata, record the embedding model, vector
    dimension and index generation in the collection metadata, then swap it in."""
    if not chunks or len(chunks) != len(vectors):
        raise ValueError(f"cannot store {len(chunks)} chunks with {len(vectors)} vectors")
    client = get_client(settings)
    build_name = settings.collection + BUILD_SUFFIX
    _delete_if_present(client, build_name)  # left behind by a Job that died earlier
    build = client.create_collection(name=build_name, metadata={
        "embed_model": settings.embed_model,
        "dimension": len(vectors[0]),
        # The API clears its semantic cache when this changes (Redis accepts only the API).
        "index_generation": str(time.time_ns()),
        "hnsw:space": "cosine",
    })
    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start:start + BATCH_SIZE]
        build.add(ids=[c.id for c in batch], documents=[c.text for c in batch],
                  embeddings=vectors[start:start + BATCH_SIZE],
                  metadatas=[c.metadata() for c in batch])
    count = int(build.count())
    if count != len(chunks):
        raise RuntimeError(f"wrote {len(chunks)} chunks but the collection holds {count}")
    _delete_if_present(client, settings.collection)
    build.modify(name=settings.collection)
    return count
