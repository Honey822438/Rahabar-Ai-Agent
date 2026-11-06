"""ChromaRetriever with a fake Chroma client and a fake Ollama: no network."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.config import Settings
from app.retrieval import chroma
from app.retrieval.chroma import ChromaRetriever, asks_for_older_version


class FakeCollection:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def query(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {
            "ids": [["rules.pdf#0001"]],
            "documents": [["5.4 Minimum CGPA is 2.00."]],
            "metadatas": [[{"source": "rules.pdf", "section": "Warning", "page": 24,
                            "doc_version": "2026", "superseded": False}]],
            "distances": [[0.25]],
        }


@pytest.fixture
def retriever(monkeypatch: pytest.MonkeyPatch) -> tuple[ChromaRetriever, FakeCollection, list]:
    collection = FakeCollection()
    posted: list[dict[str, Any]] = []

    class FakeClient:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def get_collection(self, name: str) -> FakeCollection:
            return collection

    def fake_post(url: str, json: dict[str, Any], timeout: float) -> httpx.Response:
        posted.append(json)
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2]]},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr("chromadb.HttpClient", FakeClient)
    monkeypatch.setattr(chroma.httpx, "post", fake_post)
    return ChromaRetriever(Settings(retriever="chroma")), collection, posted


def test_maps_hits_and_converts_distance_to_similarity(retriever: tuple) -> None:
    passages = retriever[0].retrieve("What is the minimum CGPA?", k=5)
    assert len(passages) == 1
    assert (passages[0].chunk_id, passages[0].page, passages[0].score) == (
        "rules.pdf#0001", 24, 0.75)
    assert retriever[1].calls[0]["n_results"] == 5


def test_uses_the_pinned_model_and_query_prefix(retriever: tuple) -> None:
    retriever[0].retrieve("What is the minimum CGPA?", k=5)
    assert retriever[2][0] == {"model": "nomic-embed-text",
                               "input": ["search_query: What is the minimum CGPA?"]}


def test_superseded_documents_are_filtered_by_default(retriever: tuple) -> None:
    retriever[0].retrieve("What is the attendance rule?", k=5)
    assert retriever[1].calls[0]["where"] == {"superseded": False}


def test_filter_is_lifted_when_an_older_version_is_asked_for(retriever: tuple) -> None:
    retriever[0].retrieve("What did the 2023 rules say about attendance?", k=5)
    assert retriever[1].calls[0]["where"] is None


@pytest.mark.parametrize("question,expected", [
    ("What did the 2023 rules say?", True),
    ("Attendance in the previous handbook?", True),
    ("What was the rule in the regulations from 2023?", True),
    ("What is the current attendance rule?", False),
    ("How many graduates were there in 2023?", False),
    ("What do the 2026 rules say?", False),
    ("I joined the old campus, what is the fee?", False),
])
def test_asks_for_older_version(question: str, expected: bool) -> None:
    assert asks_for_older_version(question) is expected
