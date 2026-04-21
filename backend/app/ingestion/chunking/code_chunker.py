import tiktoken
from tree_sitter_languages import get_parser

from app.config import settings
from app.ingestion.chunking.base import BaseChunker, TextChunk

_enc = tiktoken.get_encoding("cl100k_base")

_EXT_TO_LANG: dict[str, str] = {
    "py": "python",
    "ts": "typescript",
    "tsx": "tsx",
    "js": "javascript",
    "jsx": "javascript",
    "go": "go",
    "rs": "rust",
    "java": "java",
    "cpp": "cpp",
    "c": "c",
    "cs": "c_sharp",
    "rb": "ruby",
    "php": "php",
    "swift": "swift",
    "kt": "kotlin",
    "scala": "scala",
    "sh": "bash",
}

_TOP_LEVEL_NODE_TYPES = {
    "function_definition",
    "function_declaration",
    "method_definition",
    "class_definition",
    "class_declaration",
    "decorated_definition",
    "impl_item",
    "function_item",
    "struct_item",
    "trait_item",
}


def _lang_for_filename(filename: str) -> str | None:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _EXT_TO_LANG.get(ext)


class CodeChunker(BaseChunker):
    def __init__(
        self,
        filename: str = "code.py",
        target_tokens: int = settings.CHUNK_TARGET_TOKENS,
        overlap_tokens: int = settings.CHUNK_OVERLAP_TOKENS,
    ) -> None:
        self._filename = filename
        self._target = target_tokens
        self._overlap = overlap_tokens

    def chunk(self, text: str) -> list[TextChunk]:
        lang = _lang_for_filename(self._filename)
        if lang:
            try:
                return self._tree_sitter_chunk(text, lang)
            except Exception:
                pass
        return self._fallback_chunk(text)

    # ------------------------------------------------------------------

    def _tree_sitter_chunk(self, text: str, lang: str) -> list[TextChunk]:
        parser = get_parser(lang)
        tree = parser.parse(text.encode())
        root = tree.root_node

        top_nodes = [
            child for child in root.children if child.type in _TOP_LEVEL_NODE_TYPES
        ]
        if not top_nodes:
            return self._fallback_chunk(text)

        chunks: list[TextChunk] = []
        buffer: list[str] = []
        buffer_tokens = 0

        def flush():
            nonlocal buffer, buffer_tokens
            if buffer:
                merged = "".join(buffer).strip()
                if merged:
                    chunks.append(
                        TextChunk(
                            text=merged,
                            token_count=len(_enc.encode(merged)),
                            meta={"chunker": "code", "language": lang},
                        )
                    )
            buffer = []
            buffer_tokens = 0

        for node in top_nodes:
            node_text = text[node.start_byte:node.end_byte]
            node_tokens = len(_enc.encode(node_text))
            if buffer_tokens + node_tokens > self._target and buffer:
                flush()
            if node_tokens > self._target:
                flush()
                for sub in self._fallback_chunk(node_text):
                    sub.meta.update({"language": lang})
                    chunks.append(sub)
            else:
                buffer.append(node_text + "\n")
                buffer_tokens += node_tokens

        flush()
        return chunks or self._fallback_chunk(text)

    def _fallback_chunk(self, text: str) -> list[TextChunk]:
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
                    meta={"chunker": "code_fallback"},
                )
            )
            if end == len(tokens):
                break
            start += step
        return chunks
