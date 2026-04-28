"""Gap analysis for low-confidence query refusals."""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.curation.prompts import GAP_ANALYSIS_PROMPT
from app.providers.llm import ChatMessage, LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class GapAnalysis:
    missing_topic: str
    related_topics_present: list[str] = field(default_factory=list)
    suggested_document_types: list[str] = field(default_factory=list)
    related_document_ids: list[UUID] = field(default_factory=list)


async def analyze_gap(
    user_query: str,
    retrieved_chunks: list,  # list[RetrievedChunk] — avoid circular import
    session_factory: Callable[[], AsyncSession],
    llm_provider: LLMProvider,
) -> GapAnalysis | None:
    """Characterize what's missing from the corpus for this query.

    Returns None on any error so callers can fall back gracefully.
    """
    try:
        if not retrieved_chunks:
            chunks_block = "(no matching chunks found)"
        else:
            parts = []
            for c in retrieved_chunks[:5]:
                parts.append(
                    f"Source: {c.filename} (similarity: {c.score:.2f})\n{c.text[:300]}"
                )
            chunks_block = "\n\n---\n\n".join(parts)

        prompt = GAP_ANALYSIS_PROMPT.format(query=user_query, chunks_block=chunks_block)

        result = await llm_provider.generate(
            messages=[ChatMessage(role="user", content=prompt)],
            system_prompt="You are a helpful assistant that analyzes knowledge gaps.",
            max_tokens=512,
            temperature=0.1,
        )

        data = json.loads(result.text.strip())

        # Derive related_document_ids from the retrieved chunks (deduplicated)
        seen: set[str] = set()
        related_ids: list[UUID] = []
        for chunk in retrieved_chunks:
            if chunk.document_id not in seen:
                seen.add(chunk.document_id)
                related_ids.append(UUID(chunk.document_id))

        return GapAnalysis(
            missing_topic=data.get("missing_topic", "unknown topic"),
            related_topics_present=data.get("related_topics_present", []),
            suggested_document_types=data.get("suggested_document_types", []),
            related_document_ids=related_ids,
        )

    except Exception as exc:
        logger.warning("gap analysis failed: %s", exc)
        return None
