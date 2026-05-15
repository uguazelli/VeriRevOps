import logging

from fastapi import HTTPException


logger = logging.getLogger(__name__)


def process_chatwoot_payload(item):
    body = item.get("body", item)

    status = body.get("conversation", {}).get("status")
    message_type = body.get("message_type")
    is_private = body.get("private")
    event = body.get("event")

    should_respond = (
        status != "open"
        and message_type == "incoming"
        and is_private is False
        and event == "message_created"
    )

    reason = None

    if status == "open":
        reason = "status open"
    elif message_type != "incoming":
        reason = f"message_type {message_type}"
    elif is_private is not False:
        reason = "private message"
    elif event != "message_created":
        reason = f"event {event}"

    result = {
        "shouldBotRespond": should_respond,
        "reason": reason
    }

    logger.info("Processed Chatwoot payload: %s", result)
    if not should_respond:
        logger.info("Skipping Chatwoot response: %s", reason)

    return result


def get_message_contents(messages):
    if not isinstance(messages, list):
        return []

    return [
        message.get("content")
        for message in messages
        if isinstance(message, dict) and message.get("content")
    ]


def get_text_message_content(payload):
    body = payload.get("body", payload)
    content = body.get("content")

    if isinstance(content, str) and content.strip():
        return content.strip()

    return ""


def get_chatwoot_conversation_id(payload):
    body = payload.get("body", payload)
    conversation = body.get("conversation") or {}
    conversation_id = conversation.get("id") or body.get("conversation_id")

    if not conversation_id and is_chatwoot_conversation_payload(body):
        conversation_id = body.get("id")

    if not conversation_id:
        raise HTTPException(
            status_code=400,
            detail="Chatwoot payload is missing conversation id"
        )

    return int(conversation_id)


def is_chatwoot_conversation_payload(body):
    event = body.get("event")

    if event in {
        "conversation_status_changed",
        "conversation_updated",
        "conversation_created",
    }:
        return True

    return (
        body.get("id") is not None
        and body.get("message_type") is None
        and body.get("status") is not None
        and (
            body.get("account_id") is not None
            or body.get("inbox_id") is not None
            or body.get("meta") is not None
            or body.get("contact_inbox") is not None
        )
    )


def normalize_chatwoot_history(messages):
    if not isinstance(messages, list):
        return []

    normalized_messages = []

    for message in messages:
        if not isinstance(message, dict):
            continue

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            continue

        message_type = message.get("message_type")
        role = "assistant" if message_type == 1 else "user"
        normalized_messages.append({
            "role": role,
            "content": content.strip()
        })

    return normalized_messages


def get_message_kind(item):
    body = item.get("body", item)

    attachments = body.get("attachments") or []

    if attachments:
        message_kind = attachments[0].get("file_type", "unknown")
    else:
        message_kind = "text"

    logger.info("Chatwoot message kind: %s", message_kind)
    return message_kind


def get_first_attachment_url(item):
    body = item.get("body", item)
    attachments = body.get("attachments") or []

    if not attachments:
        return None

    attachment = attachments[0]
    for key in ("data_url", "download_url", "url", "file_url", "attachment_url"):
        url = attachment.get(key)
        if url:
            return url

    return None
