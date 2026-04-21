import re
from pathlib import Path

from app.ingestion.parsers.base import ParsedContent

_JUNK_RE = re.compile(r"^(page\s+\d+(\s+of\s+\d+)?|\d{1,4})$", re.IGNORECASE)
_EXCESS_BLANK_RE = re.compile(r"\n{3,}")
_EXCESS_SPACE_RE = re.compile(r" {2,}")

_JUNK_ELEMENT_TYPES = frozenset({"Footer", "PageNumber", "PageBreak"})


def normalize(parsed: ParsedContent, file_category: str, filename: str) -> str:
    if file_category == "code":
        lang = Path(filename).suffix.lstrip(".")
        return f"```{lang}\n{parsed.text.strip()}\n```"

    elements = parsed.structure_hints.get("elements", [])
    if not elements:
        return _clean_plain(parsed.text)

    parts: list[str] = []
    for elem in elements:
        etype = elem["type"]
        text = elem["text"].strip()
        if not text or etype in _JUNK_ELEMENT_TYPES or _JUNK_RE.fullmatch(text):
            continue
        if etype == "Title":
            parts.append(f"# {text}")
        elif etype == "Header":
            parts.append(f"## {text}")
        elif etype == "ListItem":
            parts.append(f"- {text}")
        else:
            parts.append(text)

    return "\n\n".join(parts) if parts else _clean_plain(parsed.text)


def _clean_plain(text: str) -> str:
    text = _EXCESS_BLANK_RE.sub("\n\n", text)
    text = _EXCESS_SPACE_RE.sub(" ", text)
    return text.strip()
