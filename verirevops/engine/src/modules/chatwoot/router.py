import secrets

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from src.modules.auth.service import get_tenant_by_slug_simple, get_tenant_webhook_token
from src.modules.chatwoot.message_tracking import (
    svc_list_chat_messages,
    svc_upsert_chat_message,
)
from src.modules.chatwoot.schemas import ChatMessageCreate, ChatMessageResponse
from src.modules.chatwoot.service import process_chatwoot_webhook

router = APIRouter()


async def _validate_webhook(slug: str, request: Request):
    """Verify the tenant exists and optionally check X-Webhook-Token."""
    tenant = await get_tenant_by_slug_simple(slug)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    webhook_token = await get_tenant_webhook_token(tenant.id)
    if webhook_token:
        provided = request.headers.get("X-Webhook-Token", "")
        if not provided or not secrets.compare_digest(provided, webhook_token):
            raise HTTPException(status_code=401, detail="Invalid or missing X-Webhook-Token")

    return tenant


@router.post("/chatwoot/webhook/{slug}")
async def chatwoot_webhook(
    slug: str,
    payload: dict,
    background_tasks: BackgroundTasks,
    request: Request,
):
    await _validate_webhook(slug, request)
    background_tasks.add_task(process_chatwoot_webhook, slug, payload)
    return {"status": "accepted"}


@router.post("/chat_messages", response_model=ChatMessageResponse)
async def upsert_chat_message(message_data: ChatMessageCreate):
    return await svc_upsert_chat_message(message_data)


@router.get("/chat_messages", response_model=list[ChatMessageResponse])
async def list_chat_messages(
    tenant_id: int = None,
    chatwoot_account_id: int = None,
    chatwoot_conversation_id: int = None,
):
    return await svc_list_chat_messages(tenant_id, chatwoot_account_id, chatwoot_conversation_id)
