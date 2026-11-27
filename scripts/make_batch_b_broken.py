"""Build the broken half of Batch B (A3) from the fetched corpus, reproducibly.

    python scripts/make_batch_b_broken.py      # writes data/batch_b/broken-* (+ .meta.json)

Generated, not committed (they are copies of multi-MB files). Malaika's text documents
sit next to them in data/batch_b/. Each file targets one verification check:

  broken-dup-grading-page.html        exact duplicate (sha256) of grading-page.html  -> uniqueness
  broken-dup-fee-structure-page.html  exact duplicate of fee-structure-page.html     -> uniqueness
  broken-truncated-handbook.pdf       first 40% of the handbook's bytes, no %%EOF     -> completeness/quality
  broken-corrupt-scan.pdf             %PDF header + random bytes                      -> quality
  broken-garbled-notice.txt           UTF-8 read as cp1252 twice (mojibake)           -> quality
  broken-empty-upload.md              front matter only, no body                      -> quality
"""

import json
import random
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW, OUT = ROOT / "corpus" / "raw", ROOT / "data" / "batch_b"
NOTICE = ("Notice: Mid-term examinations for all undergraduate programmes will begin on "
          "Monday. Students must carry their university ID card. Late arrival beyond "
          "fifteen minutes will not be permitted. ") * 8


def meta(name: str, doc_id: str, title: str, version: str = "2026-11") -> None:
    (OUT / f"{name}.meta.json").write_text(json.dumps(
        {"doc_id": doc_id, "title": title, "source": "batch-b (generated)", "doc_version": version},
        indent=2))


def mojibake(text: str) -> str:
    for _ in range(2):
        text = text.encode("utf-8").decode("cp1252", errors="replace")
    return text.replace("’", "’").replace(" ", "¤ÿ ")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)
    for src, doc_id in (("grading-page.html", "grading-page-mirror"),
                        ("fee-structure-page.html", "fee-structure-mirror")):
        name = f"broken-dup-{src}"
        shutil.copy2(RAW / src, OUT / name)
        meta(name, doc_id, f"Mirror of {src}")
    data = (RAW / "academic-rules-handbook-jun-2026.pdf").read_bytes()
    (OUT / "broken-truncated-handbook.pdf").write_bytes(data[: int(len(data) * 0.4)])
    meta("broken-truncated-handbook.pdf", "handbook-upload", "Handbook (partial upload)")
    (OUT / "broken-corrupt-scan.pdf").write_bytes(b"%PDF-1.7\n" + rng.randbytes(50_000))
    meta("broken-corrupt-scan.pdf", "corrupt-scan", "Scanned circular")
    (OUT / "broken-garbled-notice.txt").write_text(mojibake("“Mid-term” — " + NOTICE + "é ü ñ " * 50))
    meta("broken-garbled-notice.txt", "midterm-notice", "Mid-term notice")
    (OUT / "broken-empty-upload.md").write_text(
        "---\ntitle: Empty upload\ndoc_version: 2026-11\nsource: batch-b\n---\n\n")
    meta("broken-empty-upload.md", "empty-upload", "Empty upload")
    print("\n".join(sorted(p.name for p in OUT.glob("broken-*") if not p.name.endswith(".json"))))


if __name__ == "__main__":
    main()
