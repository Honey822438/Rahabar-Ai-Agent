"""The indexing stages, with no Chroma server, Ollama or PDF needed."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from pipeline import embed as embed_module
from pipeline import store as store_module
from pipeline.chunk import chunk, heading_of
from pipeline.clean import clean
from pipeline.config import get_settings
from pipeline.embed import embed
from pipeline.extract import extract, extract_html
from pipeline.models import Chunk, Document, Page
from pipeline.store import store

FIXTURES = Path(__file__).resolve().parents[2] / "eval" / "fixtures"


def doc(*texts: str) -> Document:
    pages = [Page("d.pdf", i, text) for i, text in enumerate(texts, start=1)]
    return Document("d.pdf", "2026", False, pages)


def test_clean_strips_repeating_headers_but_keeps_clauses() -> None:
    pages = [f"NATIONAL UNIVERSITY\n1.{i} A student must attend class.\n{i}" for i in range(1, 6)]
    text = "\n".join(page.text for page in clean(doc(*pages)).pages)
    assert "NATIONAL UNIVERSITY" not in text
    assert "1.3 A student must attend class." in text


def test_clean_treats_page_numbers_on_either_side_as_one_header() -> None:
    pages = [(f"{i} Fast-Nuces" if i % 2 else f"Fast-Nuces {i}") + f"\nBody text number {i * 7}."
             for i in range(1, 7)]
    assert "Fast-Nuces" not in "\n".join(p.text for p in clean(doc(*pages)).pages)


def test_text_outside_the_visible_page_is_ignored() -> None:
    from pipeline.extract import _pdf_page_text

    class Visible:
        def find_tables(self) -> list:
            return []

        def extract_text_lines(self, return_chars: bool) -> list[dict]:
            return [{"top": 10.0, "text": "visible"}]

    class FakePage:
        bbox = (0, 0, 100, 100)

        def within_bbox(self, box: tuple) -> Visible:
            assert box == self.bbox
            return Visible()

    assert _pdf_page_text(FakePage()) == "visible"


def test_clean_rejoins_hyphenated_and_wrapped_lines() -> None:
    assert clean(doc("Students must regis-\nter for the\ncourse.")).pages[0].text == (
        "Students must register for the course.")


def test_clean_separates_numbered_clauses() -> None:
    assert clean(doc("1.1 First rule.\n1.2 Second rule.")).pages[0].text == (
        "1.1 First rule.\n\n1.2 Second rule.")


def test_clean_drops_table_of_contents_lines() -> None:
    toc = "\n".join(f"Topic Number {i} {i + 3}" for i in range(6))
    assert "Topic Number" not in clean(doc(toc + "\nContents")).pages[0].text


@pytest.mark.parametrize("text,expected", [
    ("Attendance Requirements", "Attendance Requirements"),
    ("## 1. Attendance", "1. Attendance"),
    ("Students must attend every class", None),
    ("1.26 Minimum CGPA of 2.00 is required.", None),
    ("Grade | Points\nA | 4.0", None),
    ("SGPA = (P1*C1 + P2*C2)/C", None),
])
def test_heading_detection(text: str, expected: str | None) -> None:
    assert heading_of(text) == expected


def test_chunks_respect_size_and_keep_metadata() -> None:
    sentences = " ".join(f"Sentence number {i} is here." for i in range(200))
    source = Document("d.pdf", "2023", True, [Page("d.pdf", 7, f"Long Rules\n\n{sentences}")])
    chunks = chunk(source, 50, 10)
    assert len(chunks) > 1
    assert all(len(c.text.split()) <= 62 for c in chunks)  # size + overlap + heading
    assert {(c.section, c.page, c.doc_version, c.superseded) for c in chunks} == {
        ("Long Rules", 7, "2023", True)}
    assert len({c.id for c in chunks}) == len(chunks)


def test_neighbouring_chunks_overlap() -> None:
    words = " ".join(f"w{i}" for i in range(120))
    chunks = chunk(doc(f"Rules\n\n{words}"), 50, 10)
    assert len(set(chunks[0].text.split()) & set(chunks[1].text.split()) - {"Rules"}) == 10


def test_a_definition_is_not_split_when_it_fits() -> None:
    first, second = "word " * 30, "definition " * 30
    chunks = chunk(doc(f"Terms\n\n{first.strip()}\n\n{second.strip()}"), 40, 0)
    assert len(chunks) == 2 and chunks[1].text.count("definition") == 30


def test_long_table_repeats_its_header() -> None:
    rows = "\n".join(f"Fee {i} | {i}" for i in range(40))
    chunks = chunk(doc(f"Fees\n\nItem | Amount\n{rows}"), 30, 5)
    assert len(chunks) > 1 and all("Item | Amount" in c.text for c in chunks)


def test_overlap_must_be_smaller_than_size() -> None:
    with pytest.raises(ValueError):
        chunk(doc("Rules\n\nSome text."), 10, 10)


def test_sections_are_not_mixed() -> None:
    chunks = chunk(doc("Attendance Rules\n\nAttend class.\n\nFee Rules\n\nPay fees."), 100, 10)
    assert [c.section for c in chunks] == ["Attendance Rules", "Fee Rules"]
    assert "Attend" not in chunks[1].text


def test_html_keeps_tables_and_drops_navigation() -> None:
    text = extract_html("<nav>Menu</nav><h2>Fees</h2><table><tr><th>Item</th><th>Rs</th></tr>"
                        "<tr><td>Tuition</td><td>100</td></tr></table><script>x()</script>")
    assert "## Fees" in text and "Tuition | 100" in text
    assert "Menu" not in text and "x()" not in text


def test_fixture_markdown_flows_through_extract_clean_chunk() -> None:
    source = clean(extract(str(FIXTURES / "academic-rules-2026.md"), "2026", False))
    chunks = chunk(source, 120, 20)
    assert "doc_version" not in chunks[0].text
    assert any("1. Attendance" == c.section and "80 percent" in c.text for c in chunks)


def test_ocr_is_used_only_for_pages_without_text(monkeypatch: pytest.MonkeyPatch) -> None:
    from pipeline import extract as extract_module

    class FakePage:
        def __init__(self, text: str) -> None:
            self.text = text

        def close(self) -> None:
            pass

    class FakePdf:
        pages = [FakePage("A real text layer on this page."), FakePage("")]

        def __enter__(self) -> FakePdf:
            return self

        def __exit__(self, *args: object) -> None:
            pass

    monkeypatch.setattr("pdfplumber.open", lambda path: FakePdf())
    monkeypatch.setattr(extract_module, "_pdf_page_text", lambda page: page.text)
    monkeypatch.setattr(extract_module, "_ocr_page", lambda path, number: f"ocr {number}")
    pages = extract("scan.pdf", "2023", True).pages
    assert [(p.ocr, p.text) for p in pages] == [
        (False, "A real text layer on this page."), (True, "ocr 2")]


def test_embed_batches_and_uses_the_document_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[list[str]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        batch = httpx.Response(200, content=request.content).json()
        assert batch["model"] == "nomic-embed-text"
        sent.append(batch["input"])
        return httpx.Response(200, json={"embeddings": [[0.1]] * len(batch["input"])})

    real = httpx.Client
    monkeypatch.setattr(embed_module.httpx, "Client", lambda **kw: real(
        transport=httpx.MockTransport(respond), **kw))
    vectors = embed([f"t{i}" for i in range(40)], get_settings())
    assert len(vectors) == 40 and [len(b) for b in sent] == [32, 8]
    assert sent[0][0] == "search_document: t0"


class FakeCollection:
    def __init__(self, client: FakeClient, name: str, metadata: dict) -> None:
        self.client, self.name, self.metadata, self.ids = client, name, metadata, []
        self.drop = False

    def add(self, ids, documents, embeddings, metadatas) -> None:
        self.ids.extend(ids[:-1] if self.drop else ids)

    def count(self) -> int:
        return len(self.ids)

    def modify(self, name: str) -> None:
        self.client.collections[name] = self.client.collections.pop(self.name)
        self.name = name


class FakeClient:
    def __init__(self) -> None:
        self.collections: dict[str, FakeCollection] = {}
        self.drop_writes = False

    def delete_collection(self, name: str) -> None:
        del self.collections[name]

    def create_collection(self, name: str, metadata: dict) -> FakeCollection:
        self.collections[name] = FakeCollection(self, name, metadata)
        self.collections[name].drop = self.drop_writes
        return self.collections[name]


def _chunk() -> Chunk:
    return Chunk("d#0", "text", "d.pdf", "S", 1, "2026", False)


def test_store_records_the_pin_and_swaps_in(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient()
    client.create_collection("rahbar", {"old": True})
    monkeypatch.setattr(store_module, "get_client", lambda settings: client)
    assert store([_chunk()], [[0.1, 0.2]], get_settings()) == 1
    assert list(client.collections) == ["rahbar"]
    meta = client.collections["rahbar"].metadata
    assert meta["embed_model"] == get_settings().embed_model
    assert meta["dimension"] == 2 and meta["index_generation"]
    assert meta["hnsw:space"] == "cosine"


def test_failed_build_leaves_the_live_index_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient()
    client.create_collection("rahbar", {"old": True})
    client.drop_writes = True
    monkeypatch.setattr(store_module, "get_client", lambda settings: client)
    with pytest.raises(RuntimeError):
        store([_chunk()], [[0.1]], get_settings())
    assert client.collections["rahbar"].metadata == {"old": True}


def test_numbered_heading_is_not_joined_to_the_next_line() -> None:
    from pipeline.clean import _paragraphs

    text = _paragraphs(["5. Unacceptable Uses of Generative AI Tools", "The unacceptable use of"])
    assert text.split("\n\n") == ["5. Unacceptable Uses of Generative AI Tools",
                                   "The unacceptable use of"]
