from app.ingestion.chunking.base import BaseChunker
from app.ingestion.chunking.code_chunker import CodeChunker
from app.ingestion.chunking.markdown_chunker import MarkdownChunker


def get_chunker(file_category: str, filename: str = "file") -> BaseChunker:
    if file_category == "code":
        return CodeChunker(filename=filename)
    return MarkdownChunker()
