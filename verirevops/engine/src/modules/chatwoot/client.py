import json
import logging
from dataclasses import dataclass

import httpx
from fastapi import HTTPException

from src.modules.chatwoot.payload import get_chatwoot_conversation_id, get_message_contents
from src.modules.chatwoot.message_tracking import svc_list_chat_messages


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatwootApiContext:
    base_url: str
    account_id: str
    api_key: str

    @property
    def headers(self):
        return {
            "api_access_token": self.api_key,
            "Content-Type": "application/json",
        }

    @property
    def auth_headers(self):
        return {"api_access_token": self.api_key}

    def conversation_url(self, conversation_id: int, path: str = "") -> str:
        url = f"{self.base_url}/api/v1/accounts/{self.account_id}/conversations/{conversation_id}"

        if path:
            return f"{url}/{path.lstrip('/')}"

        return url


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


def get_chatwoot_api_context(tenant_settings) -> ChatwootApiContext:
    chatwoot_service = get_chatwoot_service(tenant_settings)
    return ChatwootApiContext(
        base_url=chatwoot_service.url.rstrip("/"),
        account_id=chatwoot_service.account_id,
        api_key=chatwoot_service.api_key,
    )


def get_last_tracked_message_id(chat_messages):
    if not chat_messages:
        return 0

    latest_message = max(
        chat_messages,
        key=lambda message: message.id or 0
    )
    return latest_message.message_id


def get_response_text(response):
    data = response.get("data") if isinstance(response, dict) else response

    if isinstance(data, str):
        return data.strip()

    if data is not None:
        return json.dumps(data, ensure_ascii=False)

    return ""


async def send_message_to_chatwoot(tenant_settings, payload, response):
    content = get_response_text(response)

    if not content:
        logger.info("Skipping Chatwoot send because response content is empty")
        return None

    chatwoot_api = get_chatwoot_api_context(tenant_settings)
    conversation_id = get_chatwoot_conversation_id(payload)
    messages_url = chatwoot_api.conversation_url(conversation_id, "messages")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.post(
            messages_url,
            headers=chatwoot_api.headers,
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
    chatwoot_api = get_chatwoot_api_context(tenant_settings)
    conversation_id = get_chatwoot_conversation_id(payload)
    status_url = chatwoot_api.conversation_url(conversation_id, "toggle_status")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.post(
            status_url,
            headers=chatwoot_api.headers,
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


async def fetch_conversation_messages_after(
    tenant_settings,
    chatwoot_conversation_id: int,
    after_message_id: int = 0,
):
    chatwoot_api = get_chatwoot_api_context(tenant_settings)
    messages_url = (
        f"{chatwoot_api.conversation_url(chatwoot_conversation_id, 'messages')}"
        f"?after={after_message_id}"
    )
    logger.info(
        "Fetching Chatwoot messages for account=%s conversation=%s after=%s",
        chatwoot_api.account_id,
        chatwoot_conversation_id,
        after_message_id
    )

    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(
            messages_url,
            headers=chatwoot_api.auth_headers,
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
        logger.info("Fetched %s Chatwoot messages", len(messages))
        return messages

    logger.info("Fetched Chatwoot messages response with unexpected shape")
    return messages


async def get_last_ten_messages(tenant_settings, payload):
    chatwoot_api = get_chatwoot_api_context(tenant_settings)
    tenant_id = tenant_settings.tenant.id
    chatwoot_account_id = int(chatwoot_api.account_id)
    chatwoot_conversation_id = get_chatwoot_conversation_id(payload)
    tracked_messages = await svc_list_chat_messages(
        tenant_id,
        chatwoot_account_id,
        chatwoot_conversation_id
    )
    after_message_id = get_last_tracked_message_id(tracked_messages)

    messages = await fetch_conversation_messages_after(
        tenant_settings,
        chatwoot_conversation_id,
        after_message_id,
    )

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
