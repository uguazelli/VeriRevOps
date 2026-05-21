import json
import logging
from typing import Any

from src.core.json_utils import parse_json_object
from src.core.prompts import CHATWOOT_CHITCHAT_PROMPT, CHATWOOT_HANDOFF_PROMPT
from src.modules.ai.text import get_chat_response
from src.modules.chatwoot.payload import normalize_chatwoot_history
from src.modules.rag import generate_chatwoot_answer_decision


logger = logging.getLogger(__name__)


def build_chatwoot_bot_response(
    data: Any = "",
    *,
    handoff_required: bool = False,
    reason=None,
    confidence=None,
    sources=None,
):
    if isinstance(data, str):
        data = data.strip()

    return {
        "data": data,
        "handoff_required": handoff_required,
        "reason": reason,
        "confidence": confidence,
        "sources": sources if isinstance(sources, list) else [],
    }


def parse_chatwoot_text_response(
    raw_response,
    *,
    error_message: str,
    handoff_required: bool = False,
    reason=None,
):
    parsed_response = parse_json_object(
        raw_response,
        fallback=lambda: {
            "data": raw_response.strip() if isinstance(raw_response, str) else ""
        },
        logger=logger,
        error_message=error_message,
    )

    return build_chatwoot_bot_response(
        parsed_response.get("data", ""),
        handoff_required=handoff_required,
        reason=reason,
    )


def build_chitchat_prompt(current_message):
    current_message_text = current_message.strip() if current_message else "EMPTY_QUERY"
    return CHATWOOT_CHITCHAT_PROMPT.format(current_message=current_message_text)


def parse_chitchat_response(raw_response):
    return parse_chatwoot_text_response(
        raw_response,
        error_message="Failed to parse Chatwoot chitchat JSON",
    )


async def respond_to_chitchat(current_message, provider: str = "gemini"):
    prompt = build_chitchat_prompt(current_message)
    raw_response = await get_chat_response(prompt, provider=provider)
    response = parse_chitchat_response(raw_response)
    logger.info("Chatwoot chitchat response: %s", response)
    return response


def build_handoff_prompt(message_history, current_message, handoff_reason=None):
    normalized_history = normalize_chatwoot_history(message_history)
    history_json = json.dumps(normalized_history, indent=2, default=str)
    current_message_text = current_message.strip() if current_message else "EMPTY_QUERY"
    reason_text = (
        handoff_reason.strip()
        if isinstance(handoff_reason, str) and handoff_reason.strip()
        else "Requires human review."
    )

    return CHATWOOT_HANDOFF_PROMPT.format(
        handoff_reason=reason_text,
        message_history=history_json,
        current_message=current_message_text,
    )


def parse_handoff_response(raw_response):
    return parse_chatwoot_text_response(
        raw_response,
        error_message="Failed to parse Chatwoot handoff JSON",
        handoff_required=True,
    )


async def respond_to_handoff(
    message_history,
    current_message,
    provider: str = "gemini",
    handoff_reason=None,
):
    prompt = build_handoff_prompt(message_history, current_message, handoff_reason)
    raw_response = await get_chat_response(prompt, provider=provider)
    response = parse_handoff_response(raw_response)
    response["reason"] = handoff_reason
    logger.info("Chatwoot handoff response: %s", response)
    return response


async def respond_with_rag(tenant_settings, current_message, provider: str = "gemini"):
    decision = await generate_chatwoot_answer_decision(
        tenant_settings.tenant.id,
        current_message,
        provider=provider,
    )
    logger.info("Chatwoot guarded RAG decision: %s", decision)

    data = decision.get("data", {}) if isinstance(decision, dict) else {}
    if data.get("handoff_required") is True:
        return build_chatwoot_bot_response(
            "",
            handoff_required=True,
            reason=data.get("reason") or "RAG answer requires human review.",
        )

    return build_chatwoot_bot_response(
        data.get("answer", ""),
        confidence=data.get("confidence"),
        sources=data.get("sources", []),
    )
