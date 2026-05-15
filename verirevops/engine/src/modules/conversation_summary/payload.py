import logging
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


def should_summarize_chatwoot_payload(payload: Dict[str, Any]) -> bool:
    body = payload.get("body", payload)
    status = get_chatwoot_status(payload)

    if status != "resolved":
        logger.info("Skipping conversation summary for status=%s", status)
        return False

    event = body.get("event")
    logger.info("Accepted conversation summary webhook event=%s status=%s", event, status)
    return True


def get_chatwoot_status(payload: Dict[str, Any]) -> Optional[str]:
    body = payload.get("body", payload)
    conversation = body.get("conversation") or {}

    status = (
        body.get("status")
        or body.get("conversation_status")
        or body.get("current_status")
        or conversation.get("status")
    )

    if isinstance(status, str):
        return status.strip().lower()

    return None


def get_latest_message_id(messages: List[Dict[str, Any]]) -> Optional[int]:
    message_ids = []

    for message in messages:
        if not isinstance(message, dict):
            continue

        message_id = message.get("id")
        if isinstance(message_id, int):
            message_ids.append(message_id)
        elif isinstance(message_id, str) and message_id.isdigit():
            message_ids.append(int(message_id))

    if not message_ids:
        return None

    return max(message_ids)


def format_messages_for_summary(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    formatted_messages = []

    for message in messages:
        if not isinstance(message, dict):
            continue

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            continue

        formatted_messages.append({
            "id": message.get("id"),
            "role": get_message_role(message),
            "content": content.strip(),
            "created_at": message.get("created_at"),
        })

    return formatted_messages


def get_message_role(message: Dict[str, Any]) -> str:
    message_type = message.get("message_type")

    if message_type == 1 or message_type == "outgoing":
        return "assistant"

    return "user"

