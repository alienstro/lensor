from pathlib import Path

import pytest

from lensor.ingest.chunker import chunk_text
from lensor.ingest.parse import EmptyDocumentError, UnsupportedFileError, parse_document

FIXTURES = Path(__file__).parent / "fixtures"

CONTRACT = "\n\n".join(
    f"{n}. Section {n}. The Supplier shall deliver the goods within {n} days. "
    f"Either party may end this Agreement with {n * 10} days notice.   The notice must be in writing."
    for n in range(1, 120)
)


def test_chunk_offsets_match_text() -> None:
    chunks = chunk_text(CONTRACT, chunk_size=128, overlap=16)

    assert len(chunks) > 5
    for chunk in chunks:
        assert CONTRACT[chunk.start_char : chunk.end_char] == chunk.text
    covered = [False] * len(CONTRACT)
    for chunk in chunks:
        for i in range(chunk.start_char, chunk.end_char):
            covered[i] = True
    missed = [i for i, ok in enumerate(covered) if not ok and not CONTRACT[i].isspace()]
    assert missed == []
    starts = [c.start_char for c in chunks]
    assert starts == sorted(starts)


def test_chunk_short_text_is_one_chunk() -> None:
    chunks = chunk_text("Governing law: Delaware.")
    assert [(c.start_char, c.end_char) for c in chunks] == [(0, 24)]


def test_parse_txt_and_pdf() -> None:
    assert parse_document("a.txt", "Price: 10 €".encode()) == "Price: 10 €"
    text = parse_document("a.PDF", (FIXTURES / "text.pdf").read_bytes())
    assert "This Agreement renews for one year." in text


def test_parse_empty_pdf_raises() -> None:
    with pytest.raises(EmptyDocumentError):
        parse_document("scan.pdf", (FIXTURES / "empty.pdf").read_bytes())
    with pytest.raises(EmptyDocumentError):
        parse_document("blank.txt", b"  \n ")


def test_parse_rejects_other_types() -> None:
    with pytest.raises(UnsupportedFileError):
        parse_document("contract.docx", b"PK...")
