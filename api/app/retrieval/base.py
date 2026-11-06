"""The retriever interface. The rest of the API only ever sees this."""

from __future__ import annotations

from typing import Protocol

from ..schemas import Passage


class Retriever(Protocol):
    name: str

    def embed(self, question: str) -> list[float]:
        """The question's vector, from the pinned model."""
        ...

    def retrieve(self, question: str, k: int, vector: list[float] | None = None) -> list[Passage]:
        """Return up to k passages, best first. Pass `vector` if it is already embedded."""
        ...

    def count(self) -> int:
        """How many chunks the index holds. Raises if the index is unreachable or missing."""
        ...

    def index_metadata(self) -> dict[str, object]:
        """What the indexer recorded: embed_model, dimension, index_generation."""
        ...
