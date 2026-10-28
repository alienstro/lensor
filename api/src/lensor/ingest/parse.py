import tempfile
from pathlib import Path

from llama_index.readers.file import PDFReader


class EmptyDocumentError(ValueError):
    """The file has no text. A scanned PDF gives this error, because v1 has no OCR."""


class UnsupportedFileError(ValueError):
    """The file is not a PDF or a TXT file."""


def parse_document(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".txt":
        text = data.decode("utf-8", errors="replace")
    elif suffix == ".pdf":
        text = _parse_pdf(data)
    else:
        raise UnsupportedFileError("Lensor reads only PDF and TXT files.")
    if not text.strip():
        raise EmptyDocumentError(
            "Lensor found no text in this file. A scanned PDF has no text layer, "
            "and Lensor cannot read it."
        )
    return text


def _parse_pdf(data: bytes) -> str:
    # PDFReader reads from a path, so write the bytes to a temporary file first.
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(data)
        tmp.flush()
        try:
            pages = PDFReader(return_full_document=False).load_data(file=Path(tmp.name))
        except Exception as exc:  # pypdf raises many error types for a bad file.
            raise EmptyDocumentError(f"Lensor could not read this PDF: {exc}") from exc
    return "\n\n".join(page.text for page in pages if page.text)
