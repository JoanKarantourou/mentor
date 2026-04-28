import re

_CHUNKS_TAG_RE = re.compile(r"<cited_chunks>(.*?)</cited_chunks>", re.DOTALL)
_WEB_TAG_RE = re.compile(r"<cited_web>(.*?)</cited_web>", re.DOTALL)


def parse_cited_chunks(text: str) -> tuple[str, list[str]]:
    """
    Extract the <cited_chunks>...</cited_chunks> tag from LLM output.
    Returns (cleaned_text, cited_chunk_ids).
    Falls back to (original_text, []) if parsing fails.
    """
    cleaned, chunk_ids, _ = parse_citations(text)
    return cleaned, chunk_ids


def parse_citations(text: str) -> tuple[str, list[str], list[int]]:
    """
    Extract both <cited_chunks> and <cited_web> tags from LLM output.
    Returns (cleaned_text, cited_chunk_ids, cited_web_indices).
    """
    chunk_ids: list[str] = []
    web_indices: list[int] = []

    match_chunks = _CHUNKS_TAG_RE.search(text)
    if match_chunks:
        raw = match_chunks.group(1).strip()
        chunk_ids = [cid.strip() for cid in raw.split(",") if cid.strip()]

    match_web = _WEB_TAG_RE.search(text)
    if match_web:
        raw = match_web.group(1).strip()
        for idx_str in raw.split(","):
            idx_str = idx_str.strip()
            try:
                web_indices.append(int(idx_str))
            except ValueError:
                pass

    cleaned = text
    if match_chunks:
        cleaned = _CHUNKS_TAG_RE.sub("", cleaned)
    if match_web:
        cleaned = _WEB_TAG_RE.sub("", cleaned)
    cleaned = cleaned.rstrip()

    return cleaned, chunk_ids, web_indices
