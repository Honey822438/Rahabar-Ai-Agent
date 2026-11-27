"""Rollback / restore (RAGOps 4.2.3): bring an archived version back as the live one.

    python -m pipeline.restore <doc_id> <version>    # then: python -m pipeline.sync

The chosen version moves archive/ -> verified/ (superseded=false); the version that was live
moves verified/ -> archive/ (superseded=true). Nothing is deleted, so a restore can itself be
undone by restoring the other version. Each restore is appended to the manifest's history.
"""

from __future__ import annotations

import sys

from .lake import Lake, entry_key, now


def restore(lake: Lake, doc_id: str, version: str) -> str:
    manifest = lake.load()
    docs = manifest["docs"]
    key = entry_key(doc_id, version)
    if key not in docs or docs[key]["status"] not in ("archived", "deleted"):
        raise SystemExit(f"{key} is not in the archive (status: {docs.get(key, {}).get('status')})")
    for other_key, entry in docs.items():
        if entry["doc_id"] == doc_id and entry["status"] == "verified":
            entry["file"] = f"archive/{lake.move(lake.root / entry['file'], 'archive', entry['version']).name}"
            entry.update(status="archived", superseded=True, updated_at=now(),
                         reasons=[f"rollback: replaced by {key}"])
    target = docs[key]
    target["file"] = f"verified/{lake.move(lake.root / target['file'], 'verified', version).name}"
    target.update(status="verified", superseded=False, updated_at=now(),
                  reasons=["restored by operator"])
    manifest.setdefault("history", []).append({"ts": now(), "action": "restore", "doc": key})
    lake.save(manifest)
    return key


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    print(f"restored {restore(Lake(), sys.argv[1], sys.argv[2])}; now run: python -m pipeline.sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
