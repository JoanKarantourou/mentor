import tiktoken
from markdown_it import MarkdownIt

from app.config import settings
from app.ingestion.chunking.base import BaseChunker, TextChunk

_enc = tiktoken.get_encoding("cl100k_base")


def _count(text: str) -> int:
    return len(_enc.encode(text))


class MarkdownChunker(BaseChunker):
    def __init__(
        self,
        target_tokens: int = settings.CHUNK_TARGET_TOKENS,
        overlap_tokens: int = settings.CHUNK_OVERLAP_TOKENS,
    ) -> None:
        self._target = target_tokens
        self._overlap = overlap_tokens
        self._md = MarkdownIt()

    def chunk(self, text: str) -> list[TextChunk]:
        sections = self._split_by_heading(text)
        chunks: list[TextChunk] = []
        for section in sections:
            chunks.extend(self._window(section))
        return chunks

    # ------------------------------------------------------------------

    def _split_by_heading(self, text: str) -> list[str]:
        """Split markdown at heading boundaries, keeping the heading with its body."""
        lines = text.splitlines(keepends=True)
        sections: list[list[str]] = []
        current: list[str] = []
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith("#") and current:
                sections.append(current)
                current = [line]
            else:
                current.append(line)
        if current:
            sections.append(current)
        return ["".join(s).strip() for s in sections if "".join(s).strip()]

    def _window(self, text: str) -> list[TextChunk]:
        """Slide a token window over a section, yielding overlapping chunks."""
        tokens = _enc.encode(text)
        if not tokens:
            return []
        step = max(1, self._target - self._overlap)
        chunks: list[TextChunk] = []
        start = 0
        while start < len(tokens):
            end = min(start + self._target, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = _enc.decode(chunk_tokens)
            chunks.append(
                TextChunk(
                    text=chunk_text,
                    token_count=len(chunk_tokens),
                    meta={"chunker": "markdown"},
                )
            )
            if end == len(tokens):
                break
            start += step
        return chunks
