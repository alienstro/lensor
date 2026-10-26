from dataclasses import dataclass

from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter


@dataclass(frozen=True)
class Chunk:
    start_char: int
    end_char: int
    text: str


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[Chunk]:
    """Split the text into chunks of about `chunk_size` tokens.

    Each chunk keeps its character offsets, so `text[start_char:end_char] == chunk.text`.
    """
    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    nodes = splitter.get_nodes_from_documents([Document(text=text)])
    chunks: list[Chunk] = []
    cursor = 0
    for node in nodes:
        content = node.get_content()
        start = node.start_char_idx
        # The splitter sets the offsets with a text search. Check them, and search again if
        # they do not match the text.
        if start is None or text[start : start + len(content)] != content:
            start = text.find(content, max(cursor - len(content), 0))
            if start < 0:
                start = text.find(content)
        if start < 0:
            raise ValueError("A chunk does not match the source text")
        chunks.append(Chunk(start_char=start, end_char=start + len(content), text=content))
        cursor = start
    return chunks
