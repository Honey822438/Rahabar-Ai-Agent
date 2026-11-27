"""Incremental sync (A2) against an in-memory fake collection. No network."""

import json
from pathlib import Path
from typing import Any

import pipeline.sync as sync_mod
from pipeline.config import get_settings
from pipeline.ingest import verify_incoming
from pipeline.lake import Lake
from pipeline.restore import restore

TEXT = "# Rules\n\n" + "A student must attend eighty percent of classes. " * 60 + "End."


class FakeCollection:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = {}
        self.metadata: dict[str, Any] = {}

    def get(self, include: list[str]) -> dict[str, Any]:
        return {"ids": list(self.rows), "metadatas": list(self.rows.values())}

    def add(self, ids, documents, embeddings, metadatas) -> None:  # type: ignore[no-untyped-def]
        self.rows.update(zip(ids, metadatas))

    def delete(self, ids: list[str]) -> None:
        for i in ids:
            self.rows.pop(i)

    def update(self, ids, metadatas) -> None:  # type: ignore[no-untyped-def]
        self.rows.update(zip(ids, metadatas))

    def modify(self, metadata: dict[str, Any]) -> None:
        self.metadata = metadata

    def count(self) -> int:
        return len(self.rows)


def put(lake: Lake, name: str, text: str, doc_id: str, version: str) -> None:
    (lake.area("incoming") / name).write_text(text)
    (lake.area("incoming") / f"{name}.meta.json").write_text(json.dumps(
        {"doc_id": doc_id, "title": name, "source": "t", "doc_version": version}))


def test_incremental_sync(tmp_path: Path, monkeypatch: Any) -> None:
    fake = FakeCollection()
    embedded: list[int] = []
    monkeypatch.setattr(sync_mod, "get_collection", lambda s: fake)
    monkeypatch.setattr("pipeline.embed.embed",
                        lambda texts, s: embedded.append(len(texts)) or [[1.0]] * len(texts))
    lake, settings = Lake(tmp_path), get_settings()
    lake.init()
    put(lake, "a.md", TEXT, "rules", "1")
    put(lake, "b.md", TEXT.replace("eighty", "ninety"), "other", "1")
    verify_incoming(lake, None)
    first = sync_mod.sync(lake, settings)
    assert first["chunks_embedded"] > 0 and first["orphans"] == 0
    assert sync_mod.sync(lake, settings)["chunks_embedded"] == 0          # unchanged → 0
    put(lake, "a.md", TEXT.replace("eighty", "seventy"), "rules", "2")   # newer version
    verify_incoming(lake, None)
    third = sync_mod.sync(lake, settings)
    assert third["chunks_superseded_flipped"] > 0 and third["orphans"] == 0
    sync_mod.delete_doc(lake, "other")
    assert sync_mod.sync(lake, settings)["orphans"] == 0
    assert not any(m["doc_id"] == "other" for m in fake.rows.values())
    restore(lake, "rules", "1")
    sync_mod.sync(lake, settings)
    live = {m["doc_version"] for m in fake.rows.values() if not m["superseded"]}
    assert live == {"1"}
