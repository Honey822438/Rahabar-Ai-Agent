"""Stage 3: Chunk. Structure-aware, with overlap.

Sections, then paragraphs, then sentences, under a target size. The unit for `size` and
`overlap` is whitespace-separated words, as a simple stand-in for tokens.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Chunk, Document

SENTENCE_END = re.compile(r"(?<=[.!?;])\s+(?=[A-Z(\d])")
NUMBERED_HEADING = re.compile(r"^\d+(?:\.\d+)*\.?\s+[A-Z]")
SMALL_WORDS = {"a", "an", "and", "at", "by", "for", "from", "in", "of", "on", "or", "the", "to",
               "under", "with"}
MAX_HEADING_WORDS = 12
DEFAULT_SECTION = "Introduction"


@dataclass
class _Block:
    section: str
    page: int
    text: str


def word_count(text: str) -> int:
    return len(text.split())


def heading_of(paragraph: str) -> str | None:
    """The heading text if this paragraph is a heading, otherwise None."""
    if paragraph.startswith("#"):
        return paragraph.lstrip("# ").strip() or None
    words = paragraph.split()
    if "\n" in paragraph or "|" in paragraph or not 0 < len(words) <= MAX_HEADING_WORDS:
        return None
    if paragraph[-1] in ".,;:?!" or "=" in paragraph or not any(c.isalpha() for c in paragraph):
        return None
    if words[-1].isdigit() or paragraph.isupper():
        return paragraph.title() if paragraph.isupper() and len(words) > 1 else None
    significant = [w for w in words if w[0].isalpha() and w.lower() not in SMALL_WORDS]
    if not significant or not (paragraph[0].isupper() or NUMBERED_HEADING.match(paragraph)):
        return None
    capitalised = sum(w[0].isupper() for w in significant)
    return paragraph if capitalised / len(significant) >= 0.75 else None


def _blocks(doc: Document) -> list[_Block]:
    section = DEFAULT_SECTION
    blocks: list[_Block] = []
    for page in doc.pages:
        for paragraph in page.text.split("\n\n"):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            heading = heading_of(paragraph)
            if heading:
                section = heading
            else:
                blocks.append(_Block(section, page.page, paragraph))
    return blocks


def _split_oversized(text: str, size: int) -> list[str]:
    """Break one paragraph into pieces of at most `size` words."""
    if word_count(text) <= size:
        return [text]
    if "|" in text and "\n" in text:
        # A long table repeats its header row in every piece, or the columns lose their meaning.
        header, *rows = text.split("\n")
        pieces, current = [], [header]
        for row in rows:
            if word_count("\n".join(current + [row])) > size and len(current) > 1:
                pieces.append("\n".join(current))
                current = [header]
            current.append(row)
        pieces.append("\n".join(current))
        return pieces
    pieces, current_text = [], ""
    for sentence in SENTENCE_END.split(text):
        if word_count(sentence) > size:
            words = sentence.split()
            if current_text:
                pieces.append(current_text)
                current_text = ""
            pieces.extend(" ".join(words[i:i + size]) for i in range(0, len(words), size))
        elif word_count(f"{current_text} {sentence}") > size:
            pieces.append(current_text)
            current_text = sentence
        else:
            current_text = f"{current_text} {sentence}".strip()
    if current_text:
        pieces.append(current_text)
    return pieces


def _tail(text: str, overlap: int) -> str:
    """The last `overlap` words, widened to a sentence start when one is close by."""
    if overlap <= 0 or "|" in text:
        return ""
    words = text.split()
    tail = " ".join(words[-overlap:])
    match = SENTENCE_END.search(tail)
    return tail[match.end():] if match and word_count(tail[match.end():]) >= overlap / 2 else tail


def chunk(doc: Document, size: int, overlap: int) -> list[Chunk]:
    """Split on sections, then paragraphs, then sentences, keeping each chunk under `size`
    words, with up to `overlap` words shared between neighbours in the same section."""
    if overlap >= size:
        raise ValueError(f"overlap ({overlap}) must be smaller than size ({size})")
    chunks: list[Chunk] = []

    def emit(section: str, page: int, body: str) -> None:
        chunks.append(Chunk(id=f"{doc.source}#{len(chunks):04d}", text=f"{section}\n{body}",
                            source=doc.source, section=section, page=page,
                            doc_version=doc.doc_version, superseded=doc.superseded))

    section, page, body, fresh = "", 0, "", False
    for block in _blocks(doc):
        if block.section != section:
            if fresh:
                emit(section, page, body)
            section, page, body, fresh = block.section, block.page, "", False
        # Leave room for the overlap, so a full-size piece can still share words with the last.
        for piece in _split_oversized(block.text, size - overlap):
            if fresh and word_count(f"{body}\n\n{piece}") > size:
                emit(section, page, body)
                body, fresh = _tail(body, overlap), False
                page = block.page
            if not fresh:
                page = block.page
            body = f"{body}\n\n{piece}".strip()
            fresh = True
    if fresh:
        emit(section, page, body)
    return chunks
