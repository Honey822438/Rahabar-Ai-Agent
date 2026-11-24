"""The data lake (RAGOps 4.2.3): one directory tree on a PVC, plus a manifest.

    <LAKE_DIR>/incoming/    new or changed files land here (with an optional <file>.meta.json)
    <LAKE_DIR>/verified/    passed verification: the single source of truth the indexer reads
    <LAKE_DIR>/quarantine/  failed verification, with the reason in the manifest; never indexed
    <LAKE_DIR>/archive/     older versions, kept (not deleted) for history and rollback
    <LAKE_DIR>/manifest.json

The manifest is keyed by "<doc_id>@<version>", so every version of a document has its
own entry: doc_id, version, file, sha256, status, reasons, chunk_ids, timestamps.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

AREAS = ("incoming", "verified", "quarantine", "archive")
STATUSES = ("verified", "quarantined", "archived")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def entry_key(doc_id: str, version: str) -> str:
    return f"{doc_id}@{version}"


class Lake:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else Path(os.environ.get("LAKE_DIR", "/data/lake"))
        self.manifest_path = self.root / "manifest.json"

    def init(self) -> None:
        for area in AREAS:
            (self.root / area).mkdir(parents=True, exist_ok=True)
        if not self.manifest_path.exists():
            self.save({"version": 1, "created_at": now(), "updated_at": now(), "docs": {}})

    def area(self, name: str) -> Path:
        return self.root / name

    def load(self) -> dict[str, Any]:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def save(self, manifest: dict[str, Any]) -> None:
        manifest["updated_at"] = now()
        tmp = self.manifest_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self.manifest_path)   # atomic: a crash never leaves half a manifest

    def incoming(self) -> list[tuple[Path, dict[str, Any]]]:
        """Files waiting in incoming/, each with its sidecar metadata (or {})."""
        found = []
        for path in sorted(self.area("incoming").iterdir()):
            if path.name.endswith(".meta.json") or path.name.startswith("."):
                continue
            sidecar = path.with_name(path.name + ".meta.json")
            meta = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.exists() else {}
            found.append((path, meta))
        return found

    def move(self, path: Path, area: str, version: str) -> Path:
        """Move a file (and its sidecar) into an area as <version>__<name>; return the new path."""
        target = self.area(area) / (path.name if path.name.startswith(f"{version}__")
                                    else f"{version}__{path.name}")
        shutil.move(str(path), target)
        sidecar = path.with_name(path.name + ".meta.json")
        if sidecar.exists():
            shutil.move(str(sidecar), target.with_name(target.name + ".meta.json"))
        return target
