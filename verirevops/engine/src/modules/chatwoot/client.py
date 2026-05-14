import json
import logging

import httpx
from fastapi import HTTPException

from src.modules.chatwoot.payload import get_chatwoot_conversation_id, get_message_contents
from src.services.chat_messages import svc_list_chat_messages


logger = logging.getLogger(__name__)


def get_chatwoot_service(tenant_settings):
    chatwoot_service = tenant_settings.tenant.services.get("chatwoot")

    if not chatwoot_service:
        raise HTTPException(
            status_code=400,
            detail="Tenant has no chatwoot service configured"
        )

    if not chatwoot_service.url or not chatwoot_service.api_key or not chatwoot_service.account_id:
        raise HTTPException(
            status_code=400,
            detail="Chatwoot service is missing url, api_key, or account_id"
        )

    return chatwoot_service


def get_last_tracked_message_id(chat_messages):
    if not chat_messages:
        return 0

    latest_message = max(
        chat_messages,
        key=lambda message: message.id or 0
    )
    return latest_message.message_id


def get_response_text(response):
    if isinstance(response, str):
        return response.strip()

    if isinstance(response, dict):
        data = response.get("data")
        if isinstance(data, str):
            return data.strip()
        if data is not None:
            return json.dumps(data, ensure_ascii=False)

    return str(response).strip()


async def send_message_to_chatwoot(tenant_settings, payload, response):
    content = get_response_text(response)

    if not content:
        logger.info("Skipping Chatwoot send because response content is empty")
        return None

    chatwoot_service = get_chatwoot_service(tenant_settings)
    conversation_id = get_chatwoot_conversation_id(payload)
    base_url = chatwoot_service.url.rstrip("/")
    messages_url = (
        f"{base_url}/api/v1/accounts/{chatwoot_service.account_id}/"
        f"conversations/{conversation_id}/messages"
    )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.post(
            messages_url,
            headers={
                "api_access_token": chatwoot_service.api_key,
                "Content-Type": "application/json"
            },
            json={
                "content": content,
                "message_type": "outgoing",
                "private": False,
                "content_type": "text",
                "content_attributes": {}
            },
            timeout=30.0
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.exception("Failed to send Chatwoot message")
        raise HTTPException(
            status_code=exc.response.status_code,
            detail="Failed to send Chatwoot message"
        ) from exc

    message = response.json()
    logger.info("Sent Chatwoot message id=%s", message.get("id"))
    return message


async def update_conversation_status_to_open(tenant_settings, payload):
    chatwoot_service = get_chatwoot_service(tenant_settings)
    conversation_id = get_chatwoot_conversation_id(payload)
    base_url = chatwoot_service.url.rstrip("/")
    status_url = (
        f"{base_url}/api/v1/accounts/{chatwoot_service.account_id}/"
        f"conversations/{conversation_id}/toggle_status"
    )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.post(
            status_url,
            headers={
                "api_access_token": chatwoot_service.api_key,
                "Content-Type": "application/json"
            },
            json={"status": "open"},
            timeout=30.0
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.exception("Failed to update Chatwoot conversation status")
        raise HTTPException(
            status_code=exc.response.status_code,
            detail="Failed to update Chatwoot conversation status"
        ) from exc

    result = response.json()
    logger.info("Updated Chatwoot conversation %s status to open", conversation_id)
    return result


async def get_last_ten_messages(tenant_settings, payload):
    chatwoot_service = get_chatwoot_service(tenant_settings)
    tenant_id = tenant_settings.tenant.id
    chatwoot_account_id = int(chatwoot_service.account_id)
    chatwoot_conversation_id = get_chatwoot_conversation_id(payload)
    tracked_messages = await svc_list_chat_messages(
        tenant_id,
        chatwoot_account_id,
        chatwoot_conversation_id
    )
    after_message_id = get_last_tracked_message_id(tracked_messages)

    base_url = chatwoot_service.url.rstrip("/")
    messages_url = (
        f"{base_url}/api/v1/accounts/{chatwoot_service.account_id}/"
        f"conversations/{chatwoot_conversation_id}/messages?after={after_message_id}"
    )
    logger.info(
        "Fetching Chatwoot messages for account=%s conversation=%s after=%s",
        chatwoot_account_id,
        chatwoot_conversation_id,
        after_message_id
    )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(
            messages_url,
            headers={"api_access_token": chatwoot_service.api_key},
            timeout=30.0
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.exception("Failed to fetch Chatwoot messages")
        raise HTTPException(
            status_code=exc.response.status_code,
            detail="Failed to fetch Chatwoot messages"
        ) from exc

    data = response.json()
    messages = data.get("payload", data) if isinstance(data, dict) else data

    if isinstance(messages, list):
        last_messages = messages[-10:]
        logger.info("Fetched %s Chatwoot messages", len(last_messages))
        logger.info(
            "Fetched Chatwoot message contents: %s",
            json.dumps(get_message_contents(last_messages), indent=2, default=str)
        )
        return last_messages

    logger.info("Fetched Chatwoot messages response with unexpected shape")
    return messages
