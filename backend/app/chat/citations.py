import re

_TAG_RE = re.compile(r"<cited_chunks>(.*?)</cited_chunks>", re.DOTALL)


def parse_cited_chunks(text: str) -> tuple[str, list[str]]:
    """
    Extract the <cited_chunks>...</cited_chunks> tag from LLM output.
    Returns (cleaned_text, cited_chunk_ids).
    Falls back to (original_text, []) if parsing fails.
    """
    match = _TAG_RE.search(text)
    if not match:
        return text, []

    raw = match.group(1).strip()
    chunk_ids = [cid.strip() for cid in raw.split(",") if cid.strip()]
    cleaned = _TAG_RE.sub("", text).rstrip()
    return cleaned, chunk_ids
