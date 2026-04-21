"""Unit tests for chunkers."""

from pathlib import Path

from app.ingestion.chunking.code_chunker import CodeChunker
from app.ingestion.chunking.markdown_chunker import MarkdownChunker

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# MarkdownChunker
# ---------------------------------------------------------------------------


def test_markdown_chunker_returns_chunks() -> None:
    text = (FIXTURES / "sample.md").read_text(encoding="utf-8")
    chunker = MarkdownChunker(target_tokens=128, overlap_tokens=16)
    chunks = chunker.chunk(text)
    assert len(chunks) >= 1
    for c in chunks:
        assert c.text.strip()
        assert c.token_count > 0
        assert c.meta["chunker"] == "markdown"


def test_markdown_chunker_empty_text() -> None:
    chunker = MarkdownChunker()
    assert chunker.chunk("") == []


def test_markdown_chunker_respects_target_tokens() -> None:
    text = " ".join(["word"] * 2000)
    chunker = MarkdownChunker(target_tokens=100, overlap_tokens=10)
    chunks = chunker.chunk(text)
    for c in chunks:
        assert c.token_count <= 100


def test_markdown_chunker_heading_split() -> None:
    text = "# Section A\nContent A\n\n# Section B\nContent B\n"
    chunker = MarkdownChunker(target_tokens=512, overlap_tokens=0)
    chunks = chunker.chunk(text)
    assert len(chunks) == 2
    assert "Section A" in chunks[0].text
    assert "Section B" in chunks[1].text


# ---------------------------------------------------------------------------
# CodeChunker
# ---------------------------------------------------------------------------


def test_code_chunker_python() -> None:
    text = (FIXTURES / "sample.py").read_text(encoding="utf-8")
    chunker = CodeChunker(filename="sample.py", target_tokens=256, overlap_tokens=32)
    chunks = chunker.chunk(text)
    assert len(chunks) >= 1
    for c in chunks:
        assert c.text.strip()
        assert c.token_count > 0


def test_code_chunker_empty() -> None:
    chunker = CodeChunker(filename="sample.py")
    assert chunker.chunk("") == []


def test_code_chunker_unknown_extension_uses_fallback() -> None:
    chunker = CodeChunker(filename="file.xyz", target_tokens=50, overlap_tokens=5)
    chunks = chunker.chunk("x = 1\n" * 200)
    assert len(chunks) >= 1
    for c in chunks:
        assert c.token_count <= 50
