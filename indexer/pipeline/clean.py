"""Stage 2: Clean. Remove artefacts without destroying structure.

Rules, applied in order:
1. Normalise ligatures, odd spaces and runs of whitespace inside a line.
2. Drop lines that repeat at the top or bottom of many pages, ignoring digits.
3. Drop bare page numbers.
4. Drop table-of-contents lines, which would otherwise out-rank the real clause.
5. Rejoin words hyphenated across lines and join wrapped lines into paragraphs.

Deliberately kept: clause numbers, headings and table rows, because citations and
exact-term retrieval depend on them.
"""

from __future__ import annotations

import re
from collections import Counter

from .models import Document, Page

EDGE_LINES = 2
REPEAT_SHARE = 0.4
MIN_PAGES_FOR_REPEATS = 3
TOC_LINE = re.compile(r"^.{3,90}?(?:\s|\.{2,})\s*\d{1,3}$")
PAGE_NUMBER = re.compile(r"^(?:page\s+)?\d{1,3}(?:\s*(?:of|/)\s*\d{1,3})?$", re.I)
LIST_START = re.compile(r"^(?:\d+(?:\.\d+)+\.?\s|\d+[.)]\s|[a-z][.)]\s|[ivx]+\)\s|[•\-*]\s|#)")
LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", " ": " ",
             "’": "'", "‘": "'", "“": '"', "”": '"', "­": ""}


def _normalise(text: str) -> str:
    for old, new in LIGATURES.items():
        text = text.replace(old, new)
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines())


def _edge_key(line: str) -> str:
    # Digits are dropped, so "2 Fast-Nuces" and "Fast-Nuces 9" count as one running header.
    return re.sub(r"\d+", "", line).strip().lower()


def _repeating_lines(pages: list[list[str]]) -> set[str]:
    if len(pages) < MIN_PAGES_FOR_REPEATS:
        return set()
    seen: Counter[str] = Counter()
    for lines in pages:
        filled = [line for line in lines if line]
        edges = [line for line in filled[:EDGE_LINES] + filled[-EDGE_LINES:]
                 if not LIST_START.match(line)]  # a clause is never a running header
        seen.update({_edge_key(line) for line in edges})
    return {key for key, n in seen.items() if n >= max(3, len(pages) * REPEAT_SHARE)}


def _is_toc_page(lines: list[str]) -> bool:
    filled = [line for line in lines if line and "|" not in line]
    hits = sum(bool(TOC_LINE.match(line)) for line in filled)
    return hits >= 5 and hits >= len(filled) * 0.5


def _paragraphs(lines: list[str]) -> str:
    """Join wrapped lines; a blank line, a clause number or a list marker starts a new one."""
    done: list[str] = []
    current = ""
    for line in lines:
        if not line or LIST_START.match(line) or "|" in line:
            if current:
                done.append(current)
            current = ""
            if "|" in line:
                # Table rows stay on their own lines, grouped as one paragraph.
                if done and "|" in done[-1]:
                    done[-1] += "\n" + line
                else:
                    done.append(line)
                continue
        if not line:
            continue
        if current.endswith("-") and line[:1].islower():
            current = current[:-1] + line
        else:
            current = f"{current} {line}".strip()
    if current:
        done.append(current)
    return "\n\n".join(done)


def clean(doc: Document) -> Document:
    """Strip repeating headers and footers; keep headings and section boundaries."""
    split = [_normalise(page.text).split("\n") for page in doc.pages]
    repeating = _repeating_lines(split)
    pages: list[Page] = []
    for page, lines in zip(doc.pages, split):
        if _is_toc_page(lines):
            lines = [line for line in lines if not TOC_LINE.match(line)]
        kept = [line for line in lines
                if not (line and (_edge_key(line) in repeating or PAGE_NUMBER.match(line)))]
        pages.append(Page(source=page.source, page=page.page, text=_paragraphs(kept), ocr=page.ocr))
    return Document(source=doc.source, doc_version=doc.doc_version, superseded=doc.superseded,
                    pages=pages)
