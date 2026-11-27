"""Ingest + verify (RAGOps 4.2.1-4.2.3): incoming/ -> verified/ | quarantine/ | archive/.

    python -m pipeline.ingest --seed ../corpus/raw      # copy the fetched corpus into incoming/
    python -m pipeline.ingest --seed ../data/batch_b    # a later batch (Markdown front matter)
    python -m pipeline.ingest                           # verify whatever is in incoming/

Writes <REPORT_DIR>/verification-<timestamp>.json and prints a per-document, per-check table.
Exit code 0 even when documents are quarantined: quarantine is the expected outcome for bad
data, not a pipeline failure.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Callable

from .lake import Lake, entry_key, now, sha256_file
from .models import Document
from .verify import (Verdict, check_completeness, check_quality, check_recency,
                     check_uniqueness, full_text)

SUFFIXES = {".pdf", ".md", ".html", ".txt"}


def log(msg: str, **fields: object) -> None:
    print(json.dumps({"ts": now(), "logger": "rahbar.ingest", "msg": msg, **fields}), flush=True)


def slug(text: str) -> str:
    text = re.sub(r"\(.*?\)", "", text)
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def front_matter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"')
    return meta


def _sources_doc_ids(raw: Path) -> dict[str, str]:
    """name -> doc_id from corpus/sources.yaml, when it sits next to raw/."""
    sources = raw.parent / "sources.yaml"
    if not sources.exists():
        return {}
    import yaml  # type: ignore[import-untyped]
    docs = yaml.safe_load(sources.read_text(encoding="utf-8")).get("documents", [])
    return {d["name"]: d["doc_id"] for d in docs if d.get("doc_id")}


def seed(lake: Lake, source_dir: Path) -> int:
    """Copy a batch into incoming/, writing a .meta.json sidecar for each file."""
    index = source_dir / "_index.json"
    items: list[tuple[Path, dict[str, Any]]] = []
    if index.exists():
        ids = _sources_doc_ids(source_dir)
        for e in json.loads(index.read_text(encoding="utf-8")):
            items.append((source_dir / e["file"], {
                "doc_id": e.get("doc_id") or ids.get(e["name"]) or slug(e["name"]),
                "title": e["name"], "source": e["url"], "doc_version": e.get("doc_version", ""),
                "fetched_at": e.get("fetched_at", "")}))
    else:
        for path in sorted(source_dir.iterdir()):
            if path.suffix.lower() not in SUFFIXES or path.name.lower().startswith("readme"):
                continue
            meta: dict[str, Any] = front_matter(path) if path.suffix.lower() == ".md" else {}
            sidecar = path.with_name(path.name + ".meta.json")
            if sidecar.exists():
                meta.update(json.loads(sidecar.read_text(encoding="utf-8")))
            meta.setdefault("doc_id", slug(meta.get("title") or path.stem))
            items.append((path, meta))
    for path, meta in items:
        shutil.copy2(path, lake.area("incoming") / path.name)
        (lake.area("incoming") / f"{path.name}.meta.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8")
    log("seeded incoming", source=str(source_dir), files=len(items))
    return len(items)


def _extract(lake: Lake, path: Path, sha256: str,
             version: str) -> tuple[Document | None, str | None]:
    from .clean import clean
    try:
        return clean(lake.extract(path, sha256, version or "unknown", False)), None
    except Exception as exc:  # any extraction error is a quality failure, not a crash
        return None, f"{type(exc).__name__}: {exc}"


def make_embedder() -> Callable[[str], list[float]]:
    from .config import get_settings
    from .embed import embed
    settings = get_settings()
    return lambda text: embed([text], settings)[0]


def verify_incoming(lake: Lake, embed_one: Callable[[str], list[float]] | None) -> list[Verdict]:
    manifest = lake.load()
    docs: dict[str, dict[str, Any]] = manifest["docs"]
    vectors_path = lake.root / "vectors.json"     # doc-level vectors for the near-dup check
    vectors: dict[str, list[float]] = (json.loads(vectors_path.read_text())
                                       if vectors_path.exists() else {})
    live = {k: e for k, e in docs.items() if e["status"] in ("verified", "archived")}
    seen_hashes = {e["sha256"]: k for k, e in live.items()}
    seen_vectors = {k: (live[k]["doc_id"], v) for k, v in vectors.items() if k in live}

    batch = lake.incoming()
    batch_versions: dict[str, list[str]] = {}
    for _, meta in batch:
        batch_versions.setdefault(str(meta.get("doc_id", "")), []).append(
            str(meta.get("doc_version", "")))

    verdicts: list[Verdict] = []
    for path, meta in batch:
        doc_id, version = str(meta.get("doc_id") or slug(path.stem)), str(meta.get("doc_version", ""))
        key = entry_key(doc_id, version or "unknown")
        verdict = Verdict(doc_id, version or "unknown", path.name, sha256_file(path))
        if key in docs and docs[key]["sha256"] == verdict.sha256:
            log("unchanged, skipped", doc=key)
            path.unlink()
            path.with_name(path.name + ".meta.json").unlink(missing_ok=True)
            continue
        started = time.perf_counter()
        doc, error = _extract(lake, path, verdict.sha256, version)
        verdict.checks["quality"] = check_quality(doc, error)
        verdict.checks["completeness"] = check_completeness(str(path), doc, meta)
        known = [e["version"] for e in live.values() if e["doc_id"] == doc_id]
        known += [v for v in batch_versions.get(doc_id, []) if v != version]
        verdict.checks["recency"] = check_recency(doc_id, verdict.version, known)
        verdict.checks["uniqueness"] = check_uniqueness(
            verdict, full_text(doc), seen_hashes, seen_vectors,
            embed_one if verdict.checks["quality"].ok else None)

        status = verdict.status
        area = {"verified": "verified", "quarantined": "quarantine", "archived": "archive"}[status]
        moved = lake.move(path, area, verdict.version)
        docs[key] = {"doc_id": doc_id, "version": verdict.version, "file": f"{area}/{moved.name}",
                     "sha256": verdict.sha256, "status": status, "reasons": verdict.reasons,
                     "superseded": status == "archived", "title": meta.get("title", ""),
                     "source": meta.get("source", ""), "pages": len(doc.pages) if doc else 0,
                     "chunk_ids": docs.get(key, {}).get("chunk_ids", []),
                     "created_at": docs.get(key, {}).get("created_at", now()), "updated_at": now()}
        if status != "quarantined":
            seen_hashes[verdict.sha256] = key
            if verdict.vector:
                vectors[key] = verdict.vector
                seen_vectors[key] = (doc_id, verdict.vector)
            live[key] = docs[key]
        if status == "verified":     # a newer version arrived: archive the older ones
            for old_key, old in list(live.items()):
                if old["doc_id"] == doc_id and old["version"] < verdict.version \
                        and old["status"] == "verified":
                    old_path = lake.root / old["file"]
                    if old_path.exists():
                        old["file"] = f"archive/{lake.move(old_path, 'archive', old['version']).name}"
                    old.update(status="archived", superseded=True, updated_at=now(),
                               reasons=[f"recency: superseded by {key}"])
                    log("archived older version", doc=old_key, by=key)
        log("verified", doc=key, status=status, reasons=verdict.reasons,
            seconds=round(time.perf_counter() - started, 2))
        verdicts.append(verdict)

    lake.save(manifest)
    vectors_path.write_text(json.dumps(vectors), encoding="utf-8")
    return verdicts


def table(verdicts: list[Verdict]) -> str:
    def cell(v: Verdict, name: str) -> str:
        check = v.checks.get(name)
        return "-" if check is None else ("PASS" if check.ok else "FAIL")
    rows = [("doc_id@version", "quality", "complete", "recency", "unique", "max_cos", "status",
             "reason")]
    for v in verdicts:
        rows.append((f"{v.doc_id}@{v.version}"[:44], cell(v, "quality"), cell(v, "completeness"),
                     cell(v, "recency"), cell(v, "uniqueness"),
                     "-" if v.max_cosine is None else f"{v.max_cosine:.3f}", v.status.upper(),
                     "; ".join(v.reasons)[:90]))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    lines = [" | ".join(c.ljust(w) for c, w in zip(r, widths)) for r in rows]
    lines.insert(1, "-+-".join("-" * w for w in widths))
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify incoming documents into the data lake.")
    parser.add_argument("--seed", type=Path, action="append", default=[],
                        help="copy this directory's documents into incoming/ first")
    parser.add_argument("--no-embed", action="store_true", help="skip the near-duplicate check")
    parser.add_argument("--report-dir", default=os.environ.get("REPORT_DIR", "eval/results"))
    args = parser.parse_args()

    lake = Lake()
    lake.init()
    for directory in args.seed:
        seed(lake, directory)
    verdicts = verify_incoming(lake, None if args.no_embed else make_embedder())

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    counts = {s: sum(v.status == s for v in verdicts) for s in ("verified", "quarantined",
                                                               "archived")}
    report = {"timestamp": now(), "lake": str(lake.root), "counts": counts,
              "documents": [v.to_json() for v in verdicts], "table": table(verdicts)}
    out = report_dir / f"verification-{stamp}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    (report_dir / f"verification-{stamp}.txt").write_text(table(verdicts) + "\n", encoding="utf-8")
    print("\n" + table(verdicts) + "\n")
    log("verification finished", report=str(out), **counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
