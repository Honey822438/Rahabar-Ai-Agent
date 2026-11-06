"""ChromaRetriever with a fake Chroma client and a fake Ollama: no network."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.config import Settings
from app.retrieval import chroma
from app.retrieval.chroma import ChromaRetriever, asks_for_older_version


ROWS = [  # closest first, as Chroma returns them
    ("rules-2026.pdf#0001", "Attendance is required.", "rules-2026.pdf", "2026-06", False, 0.1),
    ("rules-2023.pdf#0001", "Attendance was required.", "rules-2023.pdf", "2023-08", True, 0.3),
    ("old-2019.pdf#0001", "Older attendance rule.", "old-2019.pdf", "2019-01", True, 0.4),
]


class FakeCollection:
    """Applies the `superseded` filter the way Chroma does."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def query(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        rows = [r for r in ROWS if r[4] == kwargs["where"]["superseded"]][:kwargs["n_results"]]
        return {
            "ids": [[r[0] for r in rows]],
            "documents": [[r[1] for r in rows]],
            "metadatas": [[{"source": r[2], "section": "Attendance", "page": 7,
                            "doc_version": r[3], "superseded": r[4]} for r in rows]],
            "distances": [[r[5] for r in rows]],
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
    assert [(p.chunk_id, p.page, p.score) for p in passages] == [
        ("rules-2026.pdf#0001", 7, 0.9)]
    assert retriever[1].calls[0]["n_results"] == 5


def test_uses_the_pinned_model_and_query_prefix(retriever: tuple) -> None:
    retriever[0].retrieve("What is the minimum CGPA?", k=5)
    assert retriever[2][0] == {"model": "nomic-embed-text",
                               "input": ["search_query: What is the minimum CGPA?"]}


def test_superseded_documents_are_filtered_by_default(retriever: tuple) -> None:
    retriever[0].retrieve("What is the attendance rule?", k=5)
    assert retriever[1].calls[0]["where"] == {"superseded": False}


def test_named_year_ranks_that_version_first(retriever: tuple) -> None:
    passages = retriever[0].retrieve("What did the 2023 rules say about attendance?", k=5)
    assert passages[0].source == "rules-2023.pdf"
    assert {p.source for p in passages} == {"rules-2023.pdf"}


def test_old_policy_reads_only_superseded_documents(retriever: tuple) -> None:
    passages = retriever[0].retrieve("What did the old policy say about attendance?", k=5)
    assert [p.source for p in passages] == ["rules-2023.pdf", "old-2019.pdf"]


def test_a_year_with_no_document_retrieves_nothing(retriever: tuple) -> None:
    assert retriever[0].retrieve("What did the 2021 rules say about attendance?", k=5) == []


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
