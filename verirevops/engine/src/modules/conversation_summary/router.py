import secrets

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from src.modules.auth.service import get_tenant_by_slug_simple, get_tenant_webhook_token
from src.modules.conversation_summary.service import process_conversation_summary_webhook


router = APIRouter()


async def _validate_webhook(slug: str, request: Request):
    tenant = await get_tenant_by_slug_simple(slug)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    webhook_token = await get_tenant_webhook_token(tenant.id)
    if webhook_token:
        provided = request.headers.get("X-Webhook-Token", "")
        if not provided or not secrets.compare_digest(provided, webhook_token):
            raise HTTPException(status_code=401, detail="Invalid or missing X-Webhook-Token")

    return tenant


@router.post("/conversation-summary/chatwoot/{slug}")
async def summarize_chatwoot_conversation(
    slug: str,
    payload: dict,
    background_tasks: BackgroundTasks,
    request: Request,
    service_name: str = "espocrm",
):
    await _validate_webhook(slug, request)
    background_tasks.add_task(process_conversation_summary_webhook, slug, payload, service_name)
    return {"status": "accepted"}
