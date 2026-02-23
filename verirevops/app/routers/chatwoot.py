from fastapi import APIRouter, Body, BackgroundTasks
from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.core.logger import Log
from app.models.tenant import Tenant
from app.services.chatbot.service import ChatbotService
from app.services.summarization.service import SummarizationService
from app.services.crm.service import CRMService
from app.models.integration import IntegrationConfig
from app.services.tenant.service import TenantService
from app.services.integration.service import IntegrationService
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

    Log.webhook(f"Processing incoming message {payload.id} for alias '{alias}'")
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
        integration_service = IntegrationService(db)
        client = await integration_service.resolve_chatwoot_client(tenant.id)

        # Summarize Logic (Status-based)
        sum_service = SummarizationService(db, client)
        await sum_service.process_webhook_status_change(payload, tenant.id)

@router.post("/webhook/{alias}/messages")
async def handle_message_webhook(
    alias: str,
    background_tasks: BackgroundTasks,
    webhook_data: dict = Body(...)
):
    """Specific endpoint for message_created events to avoid duplication with account webhooks."""
    async with AsyncSessionLocal() as db:
        tenant_service = TenantService(db)
        tenant = await tenant_service.resolve_tenant(alias)
        if not tenant:
            return {"status": "error", "message": "Tenant not found or inactive"}

    event = webhook_data.get("event")
    Log.webhook(f"Received {event} on /messages for alias '{alias}'", direction="IN")

    if event == "message_created":
        background_tasks.add_task(process_webhook_message, webhook_data, alias)

    return {"status": "ok"}

@router.post("/webhook/{alias}/events")
async def handle_events_webhook(
    alias: str,
    background_tasks: BackgroundTasks,
    webhook_data: dict = Body(...)
):
    """Endpoint for non-message events (contacts, status changes) from account-level webhooks."""
    async with AsyncSessionLocal() as db:
        tenant_service = TenantService(db)
        tenant = await tenant_service.resolve_tenant(alias)
        if not tenant:
            return {"status": "error", "message": "Tenant not found or inactive"}

    event = webhook_data.get("event")
    Log.webhook(f"Received {event} on /events for alias '{alias}'", direction="IN")

    # 1. Handle Contact Events (CRM Sync)
    if event in ["contact_created", "contact_updated"]:
        background_tasks.add_task(process_webhook_contact, webhook_data, alias)

    # 2. Handle Status Change (Summarization)
    elif event == "conversation_status_changed":
        background_tasks.add_task(process_webhook_status_change, webhook_data, alias)

    return {"status": "ok"}