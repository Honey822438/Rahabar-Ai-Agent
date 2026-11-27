"""E3: rebuild the lake as it was BEFORE Batch B, without re-extracting (OCR) anything.

    python scripts/make_pre_batch_b_lake.py [--src data/lake] [--dst data/e3lake]

Copies the lake, removes every Batch B entry (doc version 2026-11 or unknown: the 12 Batch B
files, verified or quarantined) with its file and doc vector, and un-archives the versions
Batch B superseded (the 2022-05 faculty start-up policy becomes verified again). Chunk-id
caches are cleared so sync.py rebuilds the collection from scratch. Then E3 runs:
  sync -> suite (pre)   ingest --seed data/batch_b -> sync -> suite (post)
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH_B_VERSIONS = {"2026-11", "unknown"}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--src", type=Path, default=ROOT / "data" / "lake")
    p.add_argument("--dst", type=Path, default=ROOT / "data" / "e3lake")
    args = p.parse_args()
    if args.dst.exists():
        shutil.rmtree(args.dst)
    shutil.copytree(args.src, args.dst, ignore=shutil.ignore_patterns("cache"))
    (args.dst / "cache").symlink_to((args.src / "cache").resolve())
    manifest = json.loads((args.dst / "manifest.json").read_text(encoding="utf-8"))
    vectors = json.loads((args.dst / "vectors.json").read_text(encoding="utf-8"))
    removed = [k for k, e in manifest["docs"].items() if e["version"] in BATCH_B_VERSIONS]
    for key in removed:
        entry = manifest["docs"].pop(key)
        (args.dst / entry["file"]).unlink(missing_ok=True)
        vectors.pop(key, None)
    restored = []
    for key, entry in manifest["docs"].items():
        entry.pop("chunk_ids", None)
        reasons = " ".join(entry.get("reasons", []))
        if entry["status"] == "archived" and any(r in reasons for r in removed):
            src = args.dst / entry["file"]
            dst = args.dst / "verified" / src.name
            shutil.move(src, dst)
            entry.update(status="verified", superseded=False, reasons=[],
                         file=f"verified/{dst.name}")
            restored.append(key)
    manifest.setdefault("history", []).append({"action": "e3: pre-batch-b copy",
                                               "removed": removed, "restored": restored})
    (args.dst / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (args.dst / "vectors.json").write_text(json.dumps(vectors), encoding="utf-8")
    print(f"removed {len(removed)} Batch B entries, restored {restored}, "
          f"{len(manifest['docs'])} entries left -> {args.dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
