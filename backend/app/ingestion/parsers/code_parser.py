import asyncio
from pathlib import Path

from app.ingestion.parsers.base import ParsedContent, Parser

_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".cs": "c_sharp",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
}

# Top-level node types whose first identifier child is the declaration name
_DECL_TYPES: dict[str, frozenset[str]] = {
    "python": frozenset({"function_definition", "class_definition", "decorated_definition"}),
    "javascript": frozenset({"function_declaration", "class_declaration"}),
    "typescript": frozenset({"function_declaration", "class_declaration", "interface_declaration"}),
    "go": frozenset({"function_declaration", "method_declaration"}),
    "java": frozenset({"class_declaration", "method_declaration"}),
    "rust": frozenset({"function_item", "struct_item", "trait_item", "impl_item"}),
    "c_sharp": frozenset({"class_declaration", "method_declaration"}),
}


class CodeParser(Parser):
    async def parse(self, data: bytes, filename: str) -> ParsedContent:
        ext = Path(filename).suffix.lower()
        lang = _EXT_TO_LANG.get(ext)
        text = data.decode("utf-8", errors="replace")

        if lang is None:
            return ParsedContent(text=text, structure_hints={"language": "unknown", "declarations": []})

        declarations = await asyncio.to_thread(self._extract_declarations, data, lang)
        return ParsedContent(
            text=text,
            structure_hints={"language": lang, "declarations": declarations},
        )

    @staticmethod
    def _extract_declarations(data: bytes, lang: str) -> list[str]:
        try:
            from tree_sitter_languages import get_parser as ts_get_parser  # lazy: heavy import

            parser = ts_get_parser(lang)
            tree = parser.parse(data)
            decl_types = _DECL_TYPES.get(lang, frozenset())
            names: list[str] = []
            for child in tree.root_node.children:
                if child.type in decl_types:
                    for sub in child.children:
                        if sub.type in ("identifier", "name"):
                            names.append(sub.text.decode("utf-8", errors="replace"))
                            break
            return names
        except Exception:
            return []
