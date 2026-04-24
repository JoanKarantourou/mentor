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

LOW_CONFIDENCE_TEMPLATE = """\
I don't have enough in the indexed documents to answer that confidently.

Reason: {reason}

You could:
- Upload a document that covers this topic
- Rephrase your question to match terms used in the existing documents
- (In the future, enable web search for this question — not yet available)\
"""


def build_context_block(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for chunk in chunks:
        header = f"[chunk:{chunk.chunk_id}]\nSource: {chunk.filename}"
        parts.append(f"---\n{header}\n\n{chunk.text}\n---")
    return "\n\n".join(parts)


def build_low_confidence_response(reason: str) -> str:
    return LOW_CONFIDENCE_TEMPLATE.format(reason=reason)
