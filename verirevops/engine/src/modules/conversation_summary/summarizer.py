import json
import logging
from typing import Any

from src.core.json_utils import parse_json_object
from src.core.prompts import CHATWOOT_CONVERSATION_SUMMARY_PROMPT
from src.modules.ai.text import get_chat_response
from src.modules.conversation_summary.payload import format_messages_for_summary


logger = logging.getLogger(__name__)


def build_conversation_summary_prompt(messages: list[dict[str, Any]]) -> str | None:
    formatted_messages = format_messages_for_summary(messages)

    if not formatted_messages:
        return None

    return CHATWOOT_CONVERSATION_SUMMARY_PROMPT.format(
        messages=json.dumps(formatted_messages, indent=2, ensure_ascii=False, default=str)
    )


def parse_conversation_summary_response(raw_response: str) -> str | None:
    parsed_response = parse_json_object(
        raw_response,
        fallback=dict,
        logger=logger,
        error_message="Failed to parse conversation summary JSON",
    )
    data = parsed_response.get("data")

    if isinstance(data, str) and data.strip():
        return data.strip()

    if data is not None:
        return json.dumps(data, ensure_ascii=False)

    return None


async def summarize_chatwoot_messages(
    messages: list[dict[str, Any]],
    provider: str = "gemini",
) -> str | None:
    prompt = build_conversation_summary_prompt(messages)

    if not prompt:
        logger.info("Skipping summary because there are no text messages to summarize")
        return None

    raw_response = await get_chat_response(prompt, provider=provider)
    summary = parse_conversation_summary_response(raw_response)
    logger.info("Generated conversation summary: %s", bool(summary))
    return summary
