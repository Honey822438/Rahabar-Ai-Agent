"""Cache rules, readiness, the embedding pin and metrics, with fakes only."""

from __future__ import annotations

import fnmatch
from typing import Any

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from app.config import Settings
from app.retrieval.stub import StubRetriever
from app.schemas import Answer, Citation, Passage
from app.services.answer import answer_question
from app.services.cache import SemanticCache, is_followup, skip_cache
from app.services.telemetry import record_generation


class FakeRedis:
    def __init__(self) -> None:
        self.strings: dict[str, str] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.lists: dict[str, list[str]] = {}

    def get(self, key: str) -> str | None:
        return self.strings.get(key)

    def set(self, key: str, value: str) -> None:
        self.strings[key] = value

    def scan_iter(self, match: str) -> list[str]:
        return [k for k in self.hashes if fnmatch.fnmatch(k, match)]

    def delete(self, key: str) -> None:
        self.hashes.pop(key, None)

    def hvals(self, key: str) -> list[str]:
        return list(self.hashes.get(key, {}).values())

    def hset(self, key: str, field: str, value: str) -> None:
        self.hashes.setdefault(key, {})[field] = value

    def expire(self, key: str, seconds: int) -> None:
        pass

    def lpush(self, key: str, value: str) -> None:
        self.lists.setdefault(key, []).insert(0, value)

    def ltrim(self, key: str, start: int, end: int) -> None:
        self.lists[key] = self.lists[key][start:end + 1]

    def ping(self) -> bool:
        return True


class Down(FakeRedis):
    def get(self, key: str) -> str | None:
        raise RedisConnectionError("down")

    def ping(self) -> bool:
        raise RedisConnectionError("down")

    def lpush(self, key: str, value: str) -> None:
        raise RedisConnectionError("down")


class Index:
    """Vectors are set per question, so similarity is exact in these tests."""

    name = "fake"

    def __init__(self, score: float = 0.9) -> None:
        self.score, self.generation, self.retrievals = score, "g1", 0
        self.vectors: dict[str, list[float]] = {}
        self.fail = False

    def embed(self, question: str) -> list[float]:
        if self.fail:
            raise RuntimeError("ollama is down")
        return self.vectors.get(question, [1.0, 0.0])

    def retrieve(self, question: str, k: int, vector: list[float] | None = None) -> list[Passage]:
        self.retrievals += 1
        return [Passage(chunk_id="r#1", text="Rule.", source="r.pdf", section="S", page=1,
                        score=self.score)]

    def count(self) -> int:
        return 1

    def index_metadata(self) -> dict[str, object]:
        return {"index_generation": self.generation}


class Model:
    name = "fake-model"

    def __init__(self, answered: bool = True, fail: bool = False) -> None:
        self.answered, self.fail, self.calls = answered, fail, 0

    def generate(self, question: str, passages: list[Passage]) -> Answer:
        self.calls += 1
        if self.fail:
            raise ValueError("not JSON")
        return Answer(reasoning="r", answer=f"answer {self.calls}",
                      citations=[Citation(source="r.pdf", section="S", page=1)],
                      answered_from_context=self.answered, confidence="high")


SETTINGS = Settings(relevance_floor=0.5)
Q = "What is the attendance requirement?"


def ask(index: Index, model: Model, cache: SemanticCache | None, question: str = Q) -> Any:
    return answer_question(question, index, model, SETTINGS, cache)


@pytest.fixture
def cache() -> SemanticCache:
    return SemanticCache(FakeRedis(), threshold=0.95)


def test_second_identical_question_is_a_cache_hit(cache: SemanticCache) -> None:
    index, model = Index(), Model()
    first, second = ask(index, model, cache), ask(index, model, cache)
    assert (first.cached, second.cached) == (False, True)
    assert second.answer == first.answer and model.calls == 1 and index.retrievals == 1
    assert second.citations == first.citations and second.retrieved == first.retrieved


def test_threshold_separates_a_hit_from_a_miss(cache: SemanticCache) -> None:
    index, model = Index(), Model()
    index.vectors = {"close question": [1.0, 0.1], "far question!": [1.0, 1.0]}
    ask(index, model, cache)
    assert ask(index, model, cache, "close question").cached is True
    assert ask(index, model, cache, "far question!").cached is False


def test_reindex_invalidates_old_answers(cache: SemanticCache) -> None:
    index, model = Index(), Model()
    ask(index, model, cache)
    index.generation = "g2"
    response = ask(index, model, cache)
    assert response.cached is False and response.answer == "answer 2"
    assert list(cache.client.hashes) == ["rahbar:cache:g2"]


def test_abstention_is_not_cached(cache: SemanticCache) -> None:
    index, model = Index(score=0.1), Model()
    assert ask(index, model, cache).answered_from_context is False
    assert ask(index, model, cache).cached is False


def test_out_of_scope_answer_is_not_cached(cache: SemanticCache) -> None:
    index, model = Index(), Model(answered=False)
    ask(index, model, cache)
    assert ask(index, model, cache).cached is False and model.calls == 2


def test_failed_validation_is_not_cached(cache: SemanticCache) -> None:
    index, model = Index(), Model(fail=True)
    assert ask(index, model, cache).answered_from_context is False
    assert ask(index, model, cache).cached is False


@pytest.mark.parametrize("question", ["What about that?", "and for PhD students?",
                                      "Why is that so?", "Can you explain it?"])
def test_followups_skip_the_cache(cache: SemanticCache, question: str) -> None:
    assert is_followup(question)
    index, model = Index(), Model()
    ask(index, model, cache, question)
    assert ask(index, model, cache, question).cached is False


def test_standalone_questions_are_not_followups() -> None:
    assert not is_followup(Q)
    assert not is_followup("Is this rule in the handbook about attendance?")


def test_older_version_questions_skip_the_cache() -> None:
    assert skip_cache("What did the 2023 rules say about attendance?")


def test_turn_is_stored(cache: SemanticCache) -> None:
    ask(Index(), Model(), cache)
    assert Q in cache.client.lists["rahbar:turns"][0]


def test_redis_down_still_answers() -> None:
    response = ask(Index(), Model(), SemanticCache(Down(), threshold=0.95))
    assert response.answered_from_context is True and response.cached is False


def test_retrieval_failure_is_a_fallback_not_a_500() -> None:
    index = Index()
    index.fail = True
    response = ask(index, Model(), None)
    assert response.answered_from_context is False and response.retrieved == []


class ReadyIndex:
    name = "fake"

    def __init__(self, count: int = 5, model: str = "nomic-embed-text",
                 error: Exception | None = None) -> None:
        self._count, self.model, self.error = count, model, error

    def count(self) -> int:
        if self.error:
            raise self.error
        return self._count

    def index_metadata(self) -> dict[str, object]:
        return {"embed_model": self.model, "dimension": 768, "index_generation": "g"}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("RETRIEVER", "stub")
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.delenv("REDIS_HOST", raising=False)
    from app.main import app

    with TestClient(app) as c:
        yield c


def ready(client: TestClient, index: ReadyIndex, cache: Any = None) -> tuple[int, dict]:
    client.app.state.retriever = index
    client.app.state.settings = Settings(embed_model="nomic-embed-text")
    client.app.state.cache = cache
    r = client.get("/readyz")
    return r.status_code, r.json()["checks"]


def test_ready_when_everything_is_ok(client: TestClient) -> None:
    status, checks = ready(client, ReadyIndex(), SemanticCache(FakeRedis(), 0.95))
    assert status == 200 and set(checks.values()) == {"ok"} and "redis" in checks


def test_not_ready_on_an_empty_collection(client: TestClient) -> None:
    status, checks = ready(client, ReadyIndex(count=0))
    assert status == 503 and checks["collection"] == "collection is empty"


def test_not_ready_when_chroma_is_down(client: TestClient) -> None:
    status, checks = ready(client, ReadyIndex(error=ConnectionError("down")))
    assert status == 503 and "unreachable" in checks["chroma"]


def test_not_ready_when_redis_is_down(client: TestClient) -> None:
    status, checks = ready(client, ReadyIndex(), SemanticCache(Down(), 0.95))
    assert status == 503 and "unreachable" in checks["redis"]


def test_embed_pin_mismatch_is_not_ready_and_names_both_models(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    status, checks = ready(client, ReadyIndex(model="dummy-768"))
    assert status == 503
    assert "dummy-768" in checks["embed_pin"] and "nomic-embed-text" in checks["embed_pin"]
    assert "embedding model conflict" in caplog.text


def test_liveness_ignores_a_broken_index(client: TestClient) -> None:
    client.app.state.retriever = ReadyIndex(error=ConnectionError("down"))
    assert client.get("/healthz").status_code == 200


def test_api_starts_while_chroma_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RETRIEVER", "chroma")
    monkeypatch.setenv("CHROMA_HOST", "127.0.0.1")
    monkeypatch.setenv("CHROMA_PORT", "9")
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.delenv("REDIS_HOST", raising=False)
    from app.main import app

    with TestClient(app) as c:
        assert c.get("/healthz").status_code == 200
        assert c.get("/readyz").status_code == 503


def test_stub_retriever_reports_the_configured_pin(client: TestClient) -> None:
    assert isinstance(client.app.state.retriever, StubRetriever)
    assert client.get("/readyz").status_code == 200


def test_metrics_expose_every_required_series(client: TestClient) -> None:
    record_generation("m", 10, 4)
    client.post("/api/ask", json={"question": "What is the rule on attendance?"})
    text = client.get("/metrics").text
    for name in ("rahbar_requests_total", "rahbar_request_seconds", "rahbar_retrieval_seconds",
                 "rahbar_generation_seconds", "rahbar_cache_hit_ratio", "rahbar_abstentions_total",
                 "rahbar_fallbacks_total", 'rahbar_tokens_total{direction="in"}'):
        assert name in text


def test_one_log_line_per_request_has_the_diagnostic_fields(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO", logger="rahbar.answer")
    client.post("/api/ask", json={"question": "What is the rule on attendance?"})
    records = [r for r in caplog.records if r.getMessage() == "answered"]
    assert len(records) == 1
    for field in ("top_k", "chunk_ids", "scores", "abstained", "cached", "provider"):
        assert hasattr(records[0], field)
