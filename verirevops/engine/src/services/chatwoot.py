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

    return {
        "shouldBotRespond": should_respond,
        "reason": reason
    }


def get_message_kind(item):
    body = item.get("body", item)

    attachments = body.get("attachments") or []

    if attachments:
        return attachments[0].get("file_type", "unknown")

    return "text"