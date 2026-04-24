import logging

from app.providers.llm import ChatMessage, LLMProvider

logger = logging.getLogger(__name__)

_TITLE_SYSTEM = (
    "Summarize the user's question as a 3–6 word title suitable for a chat history list. "
    "Return only the title — no quotes, no punctuation at the end, no extra text."
)
_MAX_TITLE_LEN = 80


async def generate_title(first_user_message: str, llm_provider: LLMProvider) -> str:
    try:
        result = await llm_provider.generate(
            messages=[ChatMessage(role="user", content=first_user_message)],
            system_prompt=_TITLE_SYSTEM,
            max_tokens=20,
            temperature=0.3,
        )
        return result.text.strip()[:_MAX_TITLE_LEN]
    except Exception as exc:
        logger.warning("Title generation failed: %s", exc)
        return first_user_message[:_MAX_TITLE_LEN]
