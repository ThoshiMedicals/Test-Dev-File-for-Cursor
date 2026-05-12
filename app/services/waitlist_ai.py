from __future__ import annotations

from app.core.config import settings
from app.services.llm import ChatMessage, LlmError, chat_json


async def summarize_personalization(*, interests: list[str], optional_feedback: str | None) -> tuple[str | None, str | None]:
    """Returns (personalized_summary, model_name) for post-launch recommendations copy."""
    if not settings.openai_api_key:
        return None, None

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "personalized_message": {"type": "string", "maxLength": 900},
            "suggested_topics": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        },
        "required": ["personalized_message", "suggested_topics"],
    }
    system = (
        "You help a news platform tailor launch messaging. "
        "Given subscriber interests and optional feedback, write a short, friendly message "
        "explaining what kinds of stories they can expect, without inventing product features."
    )
    fb = (optional_feedback or "").strip()[:2000]
    user = f"Interests: {', '.join(interests) or 'general'}\nOptional feedback: {fb or 'none'}\n"
    try:
        out = await chat_json(
            model=settings.openai_model_summarize,
            messages=[ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)],
            json_schema=schema,
        )
        msg = str(out.get("personalized_message", "")).strip()
        topics = out.get("suggested_topics") or []
        if isinstance(topics, list):
            tail = "; ".join(str(t) for t in topics[:8] if t)
            summary = f"{msg} Suggested topics: {tail}" if tail else msg
        else:
            summary = msg
        return summary or None, settings.openai_model_summarize
    except LlmError:
        return None, None
