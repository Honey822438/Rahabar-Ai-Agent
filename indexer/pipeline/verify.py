"""Verification (RAGOps 4.2.2): runs after extraction, before chunking.

Each document gets pass/fail + a reason for four checks:
  quality       extraction worked; text not empty; text not garbled
  completeness  source, title, date/version and page count present; text not truncated
  recency       no newer version of the same doc_id already in the lake or in this batch
  uniqueness    no exact duplicate (sha256) and no near-duplicate (embedding cosine >= threshold)

A document fails verification if quality, completeness or uniqueness fails (→ quarantine).
A recency failure means "an older version": it is archived with superseded=true, not deleted.
"""

from __future__ import annotations

import math
import os
import string
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .models import Document

MIN_CHARS = int(os.environ.get("VERIFY_MIN_CHARS", 200))
# Share of characters that must be letters, digits, whitespace or ordinary punctuation.
# Clean English text from our corpus scores 0.97 to 1.00; mojibake / binary noise scores far lower.
MIN_CLEAN_RATIO = float(os.environ.get("VERIFY_MIN_CLEAN_RATIO", 0.90))
NEAR_DUP_THRESHOLD = float(os.environ.get("NEAR_DUP_THRESHOLD", 0.95))
SAMPLE_CHARS = 1000     # per window; three windows (25%, 50%, 75% through the text) are embedded
# and averaged, so shared cover pages / boilerplate at the start do not dominate the vector.


def sample_vector(text: str, embed_one: Callable[[str], list[float]]) -> list[float]:
    n = len(text)
    starts = sorted({max(0, min(int(n * f) - SAMPLE_CHARS // 2, n - SAMPLE_CHARS))
                     for f in (0.25, 0.5, 0.75)})
    vecs = [embed_one(text[s:s + SAMPLE_CHARS]) for s in starts]
    return [sum(col) / len(vecs) for col in zip(*vecs)]
_CLEAN = set(string.ascii_letters + string.digits + string.whitespace + string.punctuation
             + "–—‘’“”•…·°±×÷§©®™€£¥")
_ENDINGS = tuple(".!?:;)]}\"'|”’*-_`>")


@dataclass
class Check:
    ok: bool
    reason: str = ""


@dataclass
class Verdict:
    doc_id: str
    version: str
    file: str
    sha256: str
    checks: dict[str, Check] = field(default_factory=dict)
    max_cosine: float | None = None
    nearest: str | None = None
    vector: list[float] | None = None

    @property
    def status(self) -> str:
        if not all(self.checks[name].ok for name in ("quality", "completeness", "uniqueness")
                   if name in self.checks):
            return "quarantined"
        if "recency" in self.checks and not self.checks["recency"].ok:
            return "archived"
        return "verified"

    @property
    def reasons(self) -> list[str]:
        return [f"{name}: {check.reason}" for name, check in self.checks.items() if not check.ok]

    def to_json(self) -> dict[str, Any]:
        return {"doc_id": self.doc_id, "version": self.version, "file": self.file,
                "sha256": self.sha256, "status": self.status, "reasons": self.reasons,
                "checks": {k: asdict(v) for k, v in self.checks.items()},
                "max_cosine": self.max_cosine, "nearest": self.nearest}


def full_text(doc: Document | None) -> str:
    return "\n".join(page.text for page in doc.pages) if doc else ""


def check_quality(doc: Document | None, error: str | None) -> Check:
    if error or doc is None:
        return Check(False, f"extraction failed: {error}")
    text = full_text(doc)
    chars = len(text.strip())
    if chars < MIN_CHARS:
        return Check(False, f"empty: {chars} characters < {MIN_CHARS}")
    sample = [c for c in text if not c.isspace()] or ["?"]
    clean = sum(c in _CLEAN for c in sample) / len(sample)
    replacement = text.count("�") / max(len(text), 1)
    if clean < MIN_CLEAN_RATIO or replacement > 0.01:
        return Check(False, f"garbled: clean-character ratio {clean:.2f} < {MIN_CLEAN_RATIO}"
                     if clean < MIN_CLEAN_RATIO else f"garbled: {replacement:.1%} U+FFFD")
    return Check(True, f"{chars} chars, clean ratio {clean:.2f}")


def is_truncated(path: str, doc: Document) -> str:
    """Return a reason if the file looks cut off, else ''."""
    if path.lower().endswith(".pdf"):
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(handle.tell() - 2048, 0))
            if b"%%EOF" not in handle.read():
                return "PDF has no %%EOF marker (file cut off)"
        return ""
    if path.lower().endswith((".md", ".txt")):
        tail = full_text(doc).rstrip()
        if tail and not tail.endswith(_ENDINGS) and not tail[-1].isdigit():
            return f"text ends mid-sentence: ...{tail[-40:]!r}"
    return ""


def check_completeness(path: str, doc: Document | None, meta: dict[str, Any]) -> Check:
    missing = [key for key in ("source", "title", "doc_version") if not str(meta.get(key, "")).strip()
               or str(meta.get(key)).strip().lower() == "unknown"]
    if doc is None or not doc.pages:
        missing.append("page_count")
    if missing:
        return Check(False, f"missing metadata: {', '.join(missing)}")
    truncated = is_truncated(path, doc) if doc else ""
    if truncated:
        return Check(False, f"truncated: {truncated}")
    return Check(True, f"{len(doc.pages) if doc else 0} pages, version {meta['doc_version']}")


def check_recency(doc_id: str, version: str, known_versions: list[str]) -> Check:
    newer = sorted(v for v in known_versions if v > version)
    if newer:
        return Check(False, f"newer version {newer[-1]} of {doc_id} exists → archive")
    older = sorted(v for v in known_versions if v < version)
    return Check(True, f"supersedes {', '.join(older)}" if older else "latest version")


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def check_uniqueness(verdict: Verdict, text: str, seen_hashes: dict[str, str],
                     seen_vectors: dict[str, tuple[str, list[float]]],
                     embed_one: Callable[[str], list[float]] | None) -> Check:
    """seen_hashes: sha256 -> label. seen_vectors: label -> (doc_id, vector)."""
    if verdict.sha256 in seen_hashes:
        return Check(False, f"exact duplicate of {seen_hashes[verdict.sha256]} (sha256)")
    if embed_one is None or not text.strip():
        return Check(True, "sha256 unique; near-dup check skipped")
    verdict.vector = sample_vector(text, embed_one)
    best, best_label = -1.0, None
    for label, (other_doc_id, vector) in seen_vectors.items():
        if other_doc_id == verdict.doc_id:      # other versions of the same doc: recency's job
            continue
        score = cosine(verdict.vector, vector)
        if score > best:
            best, best_label = score, label
    verdict.max_cosine = round(best, 4) if best_label else None
    verdict.nearest = best_label
    if best_label and best >= NEAR_DUP_THRESHOLD:
        return Check(False, f"near-duplicate of {best_label} (cosine {best:.3f} "
                     f">= {NEAR_DUP_THRESHOLD})")
    return Check(True, f"unique (max cosine {best:.3f})" if best_label else "unique")
