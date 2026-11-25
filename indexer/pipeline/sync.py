"""Incremental index update (RAGOps 4.2.4): embed only new or changed chunks.

    python -m pipeline.sync                     # make Chroma match the lake manifest
    python -m pipeline.sync --delete <doc_id>   # remove a document (all versions) from lake + index

Chunk id = sha256(doc_id | version | chunk index | text)[:32], so the same document gives the
same ids on every run. The manifest stores each entry's chunk ids with the sha256 and chunk
config they came from: an unchanged file is not even re-extracted.

  new / changed doc    -> new ids embedded + added; the old version's ids deleted
  unchanged corpus     -> 0 chunks embedded
  archived version     -> chunks kept with superseded=true (retrieval filters them out)
  deleted / quarantined-> chunks deleted; the orphan count (chunks whose doc is not live) must be 0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from typing import Any

from .config import IndexerSettings, get_settings
from .lake import Lake, now
from .models import Chunk

LIVE = ("verified", "archived")


def log(msg: str, **fields: object) -> None:
    print(json.dumps({"ts": now(), "logger": "rahbar.sync", "msg": msg, **fields}), flush=True)


def chunk_id(doc_id: str, version: str, index: int, text: str) -> str:
    raw = f"{doc_id}|{version}|{index}|{text}".encode()
    return hashlib.sha256(raw).hexdigest()[:32]


def _extract_cached(lake: Lake, entry: dict[str, Any]) -> Any:
    """Extraction (OCR of scanned PDFs takes minutes) cached by the file's sha256 under
    <lake>/cache/: a re-chunk with another chunk config (C1 candidates) skips it."""
    from dataclasses import asdict

    from .extract import extract
    from .models import Document, Page
    path = lake.root / "cache" / f"{entry['sha256']}.json"
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Document(source=raw["source"], doc_version=entry["version"],
                        superseded=entry["superseded"],
                        pages=[Page(**p) for p in raw["pages"]])
    doc = extract(str(lake.root / entry["file"]), entry["version"], entry["superseded"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(doc)), encoding="utf-8")
    return doc


def doc_chunks(lake: Lake, entry: dict[str, Any], settings: IndexerSettings) -> list[Chunk]:
    from .chunk import chunk
    from .clean import clean
    doc = clean(_extract_cached(lake, entry))
    # The file sits in the lake as <version>__<name>; cite it by its original name.
    original = entry["file"].split("/", 1)[1].split("__", 1)[-1]
    doc.source = original
    for page in doc.pages:
        page.source = original
    pieces = chunk(doc, settings.chunk_size, settings.chunk_overlap)
    for i, piece in enumerate(pieces):
        piece.id = chunk_id(entry["doc_id"], entry["version"], i, piece.text)
    return pieces


def get_collection(settings: IndexerSettings) -> Any:
    from .store import get_client
    return get_client(settings).get_or_create_collection(name=settings.collection, metadata={
        "embed_model": settings.embed_model, "hnsw:space": "cosine",
        "index_generation": str(time.time_ns())})


def indexed(collection: Any) -> dict[str, dict[str, Any]]:
    """Every chunk id in the collection -> its metadata."""
    got = collection.get(include=["metadatas"])
    return dict(zip(got["ids"], got["metadatas"]))


def orphans(collection: Any, manifest: dict[str, Any]) -> int:
    live = {(e["doc_id"], e["version"]) for e in manifest["docs"].values() if e["status"] in LIVE}
    return sum((m.get("doc_id"), m.get("doc_version")) not in live
               for m in indexed(collection).values())


def sync(lake: Lake, settings: IndexerSettings) -> dict[str, int]:
    from .embed import embed

    manifest = lake.load()
    config = f"{settings.chunk_size}/{settings.chunk_overlap}"
    collection = get_collection(settings)
    current = indexed(collection)

    wanted: dict[str, tuple[dict[str, Any], bool]] = {}   # id -> (entry, superseded)
    new_chunks: list[Chunk] = []
    extracted = 0
    for key, entry in sorted(manifest["docs"].items()):
        if entry["status"] not in LIVE:
            continue
        cached = entry.get("chunk_ids") and entry.get("chunk_sha256") == entry["sha256"] \
            and entry.get("chunk_config") == config
        ids = list(entry["chunk_ids"]) if cached else []
        if not cached or any(i not in current for i in ids):
            pieces = doc_chunks(lake, entry, settings)
            extracted += 1
            ids = [p.id for p in pieces]
            entry.update(chunk_ids=ids, chunk_sha256=entry["sha256"], chunk_config=config,
                         updated_at=now())
            for piece in pieces:
                if piece.id not in current:
                    piece.superseded = entry["superseded"]
                    new_chunks.append(piece)
        for i in ids:
            wanted[i] = (entry, entry["superseded"])

    # 1. delete chunks whose document version is gone, changed or quarantined
    stale = [i for i in current if i not in wanted]
    for start in range(0, len(stale), 500):
        collection.delete(ids=stale[start:start + 500])
    # 2. flip superseded on chunks whose version was archived since they were indexed
    flips = [i for i, (_, sup) in wanted.items() if i in current
             and bool(current[i].get("superseded")) != sup]
    for i in flips:
        collection.update(ids=[i], metadatas=[{**current[i], "superseded": wanted[i][1]}])
    # 3. embed and add only the new chunks
    vectors = embed([c.text for c in new_chunks], settings) if new_chunks else []
    for start in range(0, len(new_chunks), 500):
        batch = new_chunks[start:start + 500]
        collection.add(ids=[c.id for c in batch], documents=[c.text for c in batch],
                       embeddings=vectors[start:start + 500],
                       metadatas=[{**c.metadata(), "doc_id": wanted[c.id][0]["doc_id"]}
                                  for c in batch])
    changed = bool(stale or flips or new_chunks)
    if changed:   # the API flushes its semantic cache when index_generation changes
        meta = {k: v for k, v in (collection.metadata or {}).items() if not k.startswith("hnsw:")}
        meta.update(embed_model=settings.embed_model, index_generation=str(time.time_ns()))
        if vectors:
            meta["dimension"] = len(vectors[0])
        collection.modify(metadata=meta)
    lake.save(manifest)
    counts = {"docs_live": sum(e["status"] in LIVE for e in manifest["docs"].values()),
              "docs_extracted": extracted, "chunks_total": int(collection.count()),
              "chunks_embedded": len(new_chunks), "chunks_deleted": len(stale),
              "chunks_superseded_flipped": len(flips), "orphans": orphans(collection, manifest)}
    return counts


def delete_doc(lake: Lake, doc_id: str) -> int:
    """Mark every version of doc_id deleted and move its files to archive/ (kept for history)."""
    manifest = lake.load()
    hits = 0
    for entry in manifest["docs"].values():
        if entry["doc_id"] == doc_id and entry["status"] != "deleted":
            path = lake.root / entry["file"]
            if path.exists() and not entry["file"].startswith("archive/"):
                entry["file"] = f"archive/{lake.move(path, 'archive', entry['version']).name}"
            entry.update(status="deleted", updated_at=now(), reasons=["deleted by operator"])
            hits += 1
    manifest.setdefault("history", []).append({"ts": now(), "action": "delete", "doc_id": doc_id})
    lake.save(manifest)
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Bring Chroma in line with the lake manifest.")
    parser.add_argument("--delete", metavar="DOC_ID", help="delete a document, then sync")
    args = parser.parse_args()
    lake, settings = Lake(), get_settings()
    if args.delete:
        log("deleting document", doc_id=args.delete, versions=delete_doc(lake, args.delete))
    started = time.perf_counter()
    counts = sync(lake, settings)
    log("sync finished", collection=settings.collection, chunk_config=f"{settings.chunk_size}/"
        f"{settings.chunk_overlap}", seconds=round(time.perf_counter() - started, 1), **counts)
    print("\n" + "\n".join(f"  {k:<26} {v}" for k, v in counts.items()) + "\n")
    return 1 if counts["orphans"] else 0


if __name__ == "__main__":
    sys.exit(main())
