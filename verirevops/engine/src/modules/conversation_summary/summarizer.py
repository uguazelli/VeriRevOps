import json
import logging
from typing import Any, Dict, List, Optional

from src.core.prompts import CHATWOOT_CONVERSATION_SUMMARY_PROMPT
from src.modules.conversation_summary.payload import format_messages_for_summary
from src.services.llm import get_chat_response


logger = logging.getLogger(__name__)


def build_conversation_summary_prompt(messages: List[Dict[str, Any]]) -> Optional[str]:
    formatted_messages = format_messages_for_summary(messages)

    if not formatted_messages:
        return None

    return CHATWOOT_CONVERSATION_SUMMARY_PROMPT.format(
        messages=json.dumps(formatted_messages, indent=2, ensure_ascii=False, default=str)
    )


def parse_conversation_summary_response(raw_response: str) -> Optional[str]:
    response_text = raw_response.strip()

    try:
        parsed_response = json.loads(response_text)
    except json.JSONDecodeError:
        start = response_text.find("{")
        end = response_text.rfind("}")

        if start == -1 or end == -1 or start >= end:
            logger.error("Failed to parse conversation summary JSON")
            return None

        try:
            parsed_response = json.loads(response_text[start:end + 1])
        except json.JSONDecodeError:
            logger.error("Failed to parse conversation summary JSON")
            return None

    data = parsed_response.get("data") if isinstance(parsed_response, dict) else None

    if isinstance(data, str) and data.strip():
        return data.strip()

    if data is not None:
        return json.dumps(data, ensure_ascii=False)

    return None


async def summarize_chatwoot_messages(
    messages: List[Dict[str, Any]],
    provider: str = "gemini",
) -> Optional[str]:
    prompt = build_conversation_summary_prompt(messages)

    if not prompt:
        logger.info("Skipping summary because there are no text messages to summarize")
        return None

    raw_response = await get_chat_response(prompt, provider=provider)
    summary = parse_conversation_summary_response(raw_response)
    logger.info("Generated conversation summary: %s", bool(summary))
    return summary
