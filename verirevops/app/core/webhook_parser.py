from typing import Optional, Tuple
from app.schemas.chat import ChatwootStatusChangePayload
from app.core.logger import Log

def parse_status_change(payload: ChatwootStatusChangePayload) -> dict:
    """
    Robustly extracts conversation and contact data from a status_change webhook.
    Returns a dict with extracted fields.
    """
    status = payload.status or (payload.conversation.status if payload.conversation else None)
    account_id = payload.account_id or (payload.account.id if payload.account else None)

    # Fallback for account_id from conversation object
    if not account_id and payload.conversation:
        account_id = payload.conversation.account_id

    conversation_id = payload.id or (payload.conversation.id if payload.conversation else None)

    if not account_id or not conversation_id or not status:
        return {}

    # 3. Resolve Contact ID (Variations in payload)
    contact_id = payload.conversation.contact_id if payload.conversation else None

    if not contact_id and payload.contact_inbox:
        contact_id = payload.contact_inbox.get("contact_id")

    if not contact_id and payload.meta:
        contact_id = payload.meta.get("sender", {}).get("id")

    # 4. Extract latest_message_id
    conv = payload.conversation
    latest_message_id = conv.last_message_id if conv else None

    if not latest_message_id and payload.messages:
        latest_message_id = payload.messages[-1].get("id")

    return {
        "account_id": int(account_id),
        "conversation_id": int(conversation_id),
        "status": status,
        "contact_id": contact_id,
        "latest_message_id": latest_message_id
    }
