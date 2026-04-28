from __future__ import annotations

from app.chat.confidence import RetrievedChunk

GROUNDED_SYSTEM_PROMPT = """\
You are Mentor, an assistant that answers questions about a team's code and documentation.

CRITICAL RULES:
1. Answer ONLY from the provided context chunks below. Do not use outside knowledge.
2. If the context does not contain enough information to answer the question, say so \
explicitly: "I don't have enough information in the indexed documents to answer this \
confidently." Do not guess or supplement with general knowledge.
3. When you cite information, reference specific chunks by their ID tag like [chunk:abc-123]. \
Only cite chunks you actually used.
4. Be concise. Developers prefer direct answers over exhaustive ones.
5. If the question is about code, show relevant code snippets from the context. \
If about documentation, quote or paraphrase from the context.
6. At the very end of your response, emit a tag listing the chunk IDs you found useful, \
in order of relevance:
   <cited_chunks>abc-123,def-456</cited_chunks>
   This tag is for the system, not the user — keep it on its own line at the very end.

The context chunks are provided below, each with a unique ID and metadata about its source.\
"""

GROUNDED_SYSTEM_PROMPT_WITH_WEB = """\
You are Mentor, an assistant that answers questions about a team's code and documentation.

You have two kinds of context available below:
- INDEXED DOCUMENTS: the team's own code and docs. These are the authoritative source \
for questions about the team's specific systems.
- WEB SEARCH RESULTS: external sources from the internet. Use these only when the indexed \
documents don't cover the question, or to supplement them with general knowledge.

CRITICAL RULES:
1. Prefer INDEXED DOCUMENTS over WEB SEARCH RESULTS when both could answer. \
The team's own docs are more authoritative for the team's own systems.
2. Be explicit about which kind of source you're using. When you cite an indexed document, \
the user trusts it more than a web result.
3. Cite chunks by ID: [chunk:abc-123] for indexed docs, [web:1] for web results (1-indexed).
4. If neither source has enough information, say so explicitly.
5. Be concise. Developers prefer direct answers over exhaustive ones.
6. At the very end of your response, emit two tags on their own lines:
   <cited_chunks>abc-123,def-456</cited_chunks>
   <cited_web>1,3</cited_web>
   Omit a tag entirely if you cited nothing from that source type.
   These tags are for the system, not the user.\
"""

LOW_CONFIDENCE_TEMPLATE = """\
I don't have enough in the indexed documents to answer that confidently.

Reason: {reason}

You could:
- Upload a document that covers this topic
- Rephrase your question to match terms used in the existing documents
- Enable web search for this question using the 🌐 toggle\
"""


def build_context_block(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for chunk in chunks:
        header = f"[chunk:{chunk.chunk_id}]\nSource: {chunk.filename}"
        parts.append(f"---\n{header}\n\n{chunk.text}\n---")
    return "\n\n".join(parts)


def build_combined_context(
    chunks: list[RetrievedChunk],
    web_results: list,
) -> str:
    """Build a combined context block with corpus chunks and/or web results."""
    parts = []

    if chunks:
        corpus_parts = []
        for chunk in chunks:
            header = f"[chunk:{chunk.chunk_id}]\nSource: {chunk.filename}"
            corpus_parts.append(f"{header}\n\n{chunk.text}")
        parts.append("=== INDEXED DOCUMENTS ===\n\n" + "\n\n---\n\n".join(corpus_parts))

    if web_results:
        web_parts = []
        for r in web_results:
            lines = [
                f"[web:{r.rank + 1}]",
                f"Title: {r.title}",
                f"URL: {r.url}",
                f"Source: {r.source_domain}",
            ]
            if r.published_date:
                lines.append(f"Published: {r.published_date}")
            header = "\n".join(lines)
            web_parts.append(f"{header}\n\n{r.snippet}")
        parts.append("=== WEB SEARCH RESULTS ===\n\n" + "\n\n---\n\n".join(web_parts))

    return "\n\n".join(parts)


def build_low_confidence_response(reason: str) -> str:
    return LOW_CONFIDENCE_TEMPLATE.format(reason=reason)
