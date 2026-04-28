"""Extract durable facts from a conversation into a saved Markdown note."""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.curation.prompts import MEMORY_EXTRACTION_FALLBACK_PROMPT, MEMORY_EXTRACTION_PROMPT
from app.providers.llm import ChatMessage, LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class ExtractedMemory:
    title: str
    content: str                      # Full Markdown note body
    source_message_ids: list[UUID] = field(default_factory=list)
    fact_count: int = 0


async def extract_memory(
    conversation_id: UUID,
    session_factory: Callable[[], AsyncSession],
    llm_provider: LLMProvider,
) -> ExtractedMemory:
    """Extract durable facts from a conversation into a Markdown note."""
    async with session_factory() as session:
        result = await session.execute(
            text("""
                SELECT id, role, content
                FROM messages
                WHERE conversation_id = :cid
                ORDER BY message_index
            """),
            {"cid": str(conversation_id)},
        )
        rows = result.all()

    if not rows:
        return ExtractedMemory(title="Empty conversation", content="No messages to extract.", fact_count=0)

    conversation_text = "\n\n".join(
        f"[{i}] {r.role.upper()}: {r.content}" for i, r in enumerate(rows)
    )
    message_ids = [UUID(str(r.id)) for r in rows]

    # Primary attempt: structured JSON output
    try:
        result_text = await _generate(
            llm_provider,
            system=MEMORY_EXTRACTION_PROMPT,
            user=f"Here is the conversation:\n\n{conversation_text}",
        )
        data = json.loads(result_text)
        title = data["title"].strip()
        facts = data.get("facts", [])
        if not facts:
            return ExtractedMemory(title=title, content="_No durable facts identified._", fact_count=0)

        # Collect source message IDs from indices
        source_indices: set[int] = set()
        for f in facts:
            for idx in f.get("source_message_indices", []):
                if 0 <= idx < len(message_ids):
                    source_indices.add(idx)

        body = "\n".join(f"- {f['content']}" for f in facts)
        return ExtractedMemory(
            title=title,
            content=body,
            source_message_ids=[message_ids[i] for i in sorted(source_indices)],
            fact_count=len(facts),
        )
    except Exception as exc:
        logger.warning("memory extraction JSON parse failed (%s), using fallback", exc)

    # Fallback: plain Markdown note, no source-message provenance
    try:
        result_text = await _generate(
            llm_provider,
            system=MEMORY_EXTRACTION_FALLBACK_PROMPT,
            user=f"Here is the conversation:\n\n{conversation_text}",
        )
        title = _extract_heading(result_text) or "Conversation notes"
        return ExtractedMemory(title=title, content=result_text, fact_count=0)
    except Exception as exc:
        logger.error("memory extraction fallback also failed: %s", exc)
        raise


async def _generate(llm_provider: LLMProvider, system: str, user: str) -> str:
    result = await llm_provider.generate(
        messages=[ChatMessage(role="user", content=user)],
        system_prompt=system,
        max_tokens=1024,
        temperature=0.2,
    )
    return result.text.strip()


def _extract_heading(text: str) -> str | None:
    m = re.search(r"^#{1,3}\s+(.+)$", text, re.MULTILINE)
    return m.group(1).strip() if m else None
