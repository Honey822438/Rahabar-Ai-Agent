"""Stage 1: Extract. PDF (or HTML, or Markdown) to text, page by page.

Pages keep their paragraph breaks as blank lines, and tables come out as `a | b | c`
rows, because the chunker and the citations depend on both.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from statistics import median
from typing import Any

from .models import Document, Page

# Below this many characters a page has no usable text layer, so it is OCR'd.
MIN_TEXT_CHARS = 20
OCR_DPI = 200
HTML_SKIP = {"script", "style", "nav", "header", "footer", "noscript", "svg", "form", "button"}
HTML_BLOCK = {"p", "div", "li", "section", "article", "br", "ul", "ol", "main"}


def _table_text(rows: list[list[str | None]]) -> str:
    lines = []
    for row in rows:
        cells = [" ".join((cell or "").split()) for cell in row]
        if any(cells):
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def _pdf_page_text(page: Any) -> str:
    """Text lines and tables in reading order, with a blank line at each paragraph gap."""
    # The handbooks hold hidden text beyond the visible page, which pdfplumber returns unless
    # cropped; without this, each page is interleaved with text from another.
    page = page.within_bbox(page.bbox)
    tables = [t for t in page.find_tables() if len(t.rows) >= 2 and len(t.rows[0].cells) >= 2]
    boxes = [t.bbox for t in tables]

    def outside_tables(obj: dict[str, Any]) -> bool:
        cx, cy = (obj["x0"] + obj["x1"]) / 2, (obj["top"] + obj["bottom"]) / 2
        return not any(x0 <= cx <= x1 and top <= cy <= bottom for x0, top, x1, bottom in boxes)

    body = page.filter(outside_tables) if boxes else page
    lines = body.extract_text_lines(return_chars=False)
    gaps = [b["top"] - a["top"] for a, b in zip(lines, lines[1:]) if b["top"] > a["top"]]
    usual_gap = median(gaps) if gaps else 0.0

    blocks: list[tuple[float, str]] = []
    previous_top: float | None = None
    for line in lines:
        wide_gap = previous_top is not None and line["top"] - previous_top > usual_gap * 1.5
        blocks.append((line["top"], ("\n" if wide_gap else "") + line["text"]))
        previous_top = line["top"]
    for table, box in zip(tables, boxes):
        text = _table_text(table.extract())
        if text:
            blocks.append((box[1], f"\n{text}\n"))
    blocks.sort(key=lambda block: block[0])
    return "\n".join(text for _, text in blocks)


def _ocr_page(path: str, number: int) -> str:
    # One page at a time: rendering a whole scan at once is what OOMKills the Job.
    import pytesseract
    from pdf2image import convert_from_path

    image = convert_from_path(path, dpi=OCR_DPI, first_page=number, last_page=number,
                              grayscale=True)[0]
    return str(pytesseract.image_to_string(image))


def _extract_pdf(path: str) -> list[Page]:
    import pdfplumber

    source = Path(path).name
    pages: list[Page] = []
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            text = _pdf_page_text(page)
            ocr = len(text.strip()) < MIN_TEXT_CHARS
            if ocr:
                text = _ocr_page(path, number)
            pages.append(Page(source=source, page=number, text=text, ocr=ocr))
            page.close()
    return pages


class _HtmlText(HTMLParser):
    """Visible text only. Headings become Markdown headings and tables become rows."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0
        self.row: list[str] | None = None
        self.cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in HTML_SKIP:
            self.skip += 1
        elif self.skip:
            return
        elif re.fullmatch(r"h[1-6]", tag):
            self.parts.append(f"\n\n{'#' * int(tag[1])} ")
        elif tag == "table":
            self.parts.append("\n\n")
        elif tag == "tr":
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = []
        elif tag in HTML_BLOCK:
            self.parts.append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in HTML_SKIP:
            self.skip = max(0, self.skip - 1)
        elif self.skip:
            return
        elif re.fullmatch(r"h[1-6]", tag):
            self.parts.append("\n\n")
        elif tag in {"td", "th"} and self.row is not None and self.cell is not None:
            self.row.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if any(self.row):
                self.parts.append(" | ".join(self.row) + "\n")
            self.row = None
        elif tag == "table":
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        if self.cell is not None:
            self.cell.append(data)
        elif self.row is None and data.strip():
            self.parts.append(" ".join(data.split()) + " ")


def extract_html(markup: str) -> str:
    parser = _HtmlText()
    parser.feed(markup)
    return "".join(parser.parts)


def strip_front_matter(text: str) -> str:
    return re.sub(r"\A---\n.*?\n---\n", "", text, count=1, flags=re.S)


def extract(path: str, doc_version: str, superseded: bool) -> Document:
    """Return the document's text page by page; OCR'd pages are marked ocr=True."""
    file = Path(path)
    suffix = file.suffix.lower()
    if suffix == ".pdf":
        pages = _extract_pdf(path)
    else:
        raw = file.read_text(encoding="utf-8", errors="replace")
        text = extract_html(raw) if suffix in {".html", ".htm"} else strip_front_matter(raw)
        pages = [Page(source=file.name, page=1, text=text)]
    return Document(source=file.name, doc_version=doc_version, superseded=superseded, pages=pages)
