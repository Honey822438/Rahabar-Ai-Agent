"""C1: build a candidate collection from the lake with a different chunk config.

    python scripts/build_collection.py --collection rahbar_c600 --chunk-size 600 --overlap 100

The candidate gets its OWN Chroma collection; the baseline `rahbar` is never touched. sync.py
caches chunk ids per chunk config in the lake manifest, so the sync runs on a throwaway copy of
the lake (the real manifest keeps its 400/50 cache). Same extractor, cleaner, embedder and
embedding model as the baseline: chunk size/overlap is the only change.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--collection", required=True)
    p.add_argument("--chunk-size", type=int, required=True)
    p.add_argument("--overlap", type=int, required=True)
    p.add_argument("--lake", type=Path, default=ROOT / "data" / "lake")
    args = p.parse_args()
    if args.collection == os.environ.get("BASELINE_COLLECTION", "rahbar"):
        sys.exit("refusing to rebuild the baseline collection")
    with tempfile.TemporaryDirectory(prefix="lake-copy-") as tmp:
        lake = Path(tmp) / "lake"
        shutil.copytree(args.lake, lake, ignore=shutil.ignore_patterns("cache"))
        (args.lake / "cache").mkdir(exist_ok=True)
        (lake / "cache").symlink_to((args.lake / "cache").resolve())   # shared OCR cache
        env = {**os.environ, "LAKE_DIR": str(lake), "CHROMA_COLLECTION": args.collection,
               "CHUNK_SIZE": str(args.chunk_size), "CHUNK_OVERLAP": str(args.overlap),
               "CHROMA_HOST": os.environ.get("CHROMA_HOST", "localhost"),
               "CHROMA_PORT": os.environ.get("CHROMA_PORT", "8001"),
               "OLLAMA_URL": os.environ.get("OLLAMA_URL", "http://localhost:11434")}
        return subprocess.run([sys.executable, "-m", "pipeline.sync"], cwd=ROOT / "indexer",
                              env=env).returncode


if __name__ == "__main__":
    sys.exit(main())
