from fastapi import APIRouter, Body, BackgroundTasks
from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.core.logger import Log
from app.models.tenant import Tenant
from app.services.chatbot_service import ChatbotService
from app.services.summarization.service import SummarizationService
from app.services.crm.service import CRMService
from app.models.integration import IntegrationConfig
from app.services.tenant_service import TenantService
from app.schemas.chat import ChatwootMessagePayload, ChatwootContactPayload, ChatwootStatusChangePayload
from typing import Optional

router = APIRouter(prefix="/api", tags=["chatwoot"])



async def process_webhook_message(data: dict, alias: str):
    try:
        payload = ChatwootMessagePayload(**data)
    except Exception as e:
        Log.error(f"Failed to parse Chatwoot message webhook: {e}")
        return

    if payload.message_type != "incoming" or payload.private:
        return

    async with AsyncSessionLocal() as db:
        service = ChatbotService(db)
        await service.process_webhook_message(payload, alias)

async def process_webhook_contact(data: dict, alias: str):
    try:
        payload = ChatwootContactPayload(**data)
    except Exception as e:
        Log.error(f"Failed to parse Chatwoot contact webhook: {e}")
        return

    async with AsyncSessionLocal() as db:
        tenant_service = TenantService(db)
        tenant = await tenant_service.resolve_tenant(alias)
        if not tenant:
            return

        service = CRMService(db)
        await service.sync_contact(tenant.id, payload)

async def process_webhook_status_change(data: dict, alias: str):
    try:
        payload = ChatwootStatusChangePayload(**data)
    except Exception as e:
        Log.error(f"Failed to parse Chatwoot status change webhook: {e}")
        return

    async with AsyncSessionLocal() as db:
        tenant_service = TenantService(db)
        tenant = await tenant_service.resolve_tenant(alias)
        if not tenant:
            return

        # Resolve Chatwoot Client
        chatbot_service = ChatbotService(db)
        client = await chatbot_service._resolve_client(tenant.id)

        # Summarize Logic (Status-based)
        sum_service = SummarizationService(db, client)
        await sum_service.process_webhook_status_change(payload, tenant.id)

@router.post("/webhook/{alias}")
async def handle_webhook(
    alias: str,
    background_tasks: BackgroundTasks,
    webhook_data: dict = Body(...)
):
    async with AsyncSessionLocal() as db:
        tenant_service = TenantService(db)
        tenant = await tenant_service.resolve_tenant(alias)
        if not tenant:
            return {"status": "error", "message": "Tenant not found or inactive"}

    event = webhook_data.get("event")

    # 1. Handle Message Events (Chatbot)
    if event == "message_created":
        background_tasks.add_task(process_webhook_message, webhook_data, alias)

    # 2. Handle Contact Events (CRM Sync)
    elif event in ["contact_created", "contact_updated"]:
        background_tasks.add_task(process_webhook_contact, webhook_data, alias)

    # 3. Handle Status Change (Summarization)
    elif event == "conversation_status_changed":
        background_tasks.add_task(process_webhook_status_change, webhook_data, alias)

    return {"status": "ok"}