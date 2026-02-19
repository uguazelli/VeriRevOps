from fastapi import APIRouter, Body, BackgroundTasks
from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.core.logger import Log
from app.models.tenant import Tenant
from app.services.chatbot_service import ChatbotService
from app.services.crm.service import CRMService

router = APIRouter(prefix="/api", tags=["chatwoot"])

async def _resolve_tenant_id(db, alias: str) -> int:
    """Helper to resolve tenant ID from slug."""
    stmt = select(Tenant.id).where(Tenant.slug == alias)
    result = await db.execute(stmt)
    return result.scalars().first()

async def process_webhook_message(data: dict, alias: str):
    """Processes incoming messages for the chatbot."""
    message_type = data.get("message_type")
    private = data.get("private", False)

    if message_type != "incoming" or private:
        return

    async with AsyncSessionLocal() as db:
        service = ChatbotService(db)
        await service.process_webhook_message(data, alias)

async def process_webhook_contact(data: dict, alias: str):
    """Processes contact events for CRM synchronization."""
    async with AsyncSessionLocal() as db:
        tenant_id = await _resolve_tenant_id(db, alias)
        if not tenant_id:
            Log.error(f"Tenant not found for alias: {alias}")
            return

        service = CRMService(db)
        await service.sync_contact(tenant_id, data)

@router.post("/webhook/{alias}")
async def handle_webhook(
    alias: str,
    background_tasks: BackgroundTasks,
    webhook_data: dict = Body(...)
):
    event = webhook_data.get("event")

    # 1. Handle Message Events (Chatbot)
    if event == "message_created":
        background_tasks.add_task(process_webhook_message, webhook_data, alias)

    # 2. Handle Contact Events (CRM Sync)
    elif event in ["contact_created", "contact_updated"]:
        background_tasks.add_task(process_webhook_contact, webhook_data, alias)

    return {"status": "ok"}