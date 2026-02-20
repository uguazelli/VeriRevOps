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

async def process_webhook_status_change(data: dict, alias: str):
    """Processes conversation status changes for summarization."""
    # Chatwoot status changed hook
    status = data.get("status")

    # Hyper-robust extraction for status change event
    account_id = data.get("account_id")
    if not account_id:
        account_id = data.get("account", {}).get("id")
    if not account_id:
        # Fallback to conversation object
        conv = data.get("conversation", {})
        account_id = conv.get("account_id") or conv.get("account", {}).get("id")

    if not account_id and data.get("messages"):
        msgs = data.get("messages", [])
        if msgs and isinstance(msgs, list):
            account_id = msgs[0].get("account_id")

    conversation_id = data.get("id") # Top level ID for status changed event
    if not conversation_id or not isinstance(conversation_id, int):
        conversation_id = data.get("conversation", {}).get("id")

    # Robust contact_id extraction
    contact_id = data.get("contact_inbox", {}).get("contact_id")
    if not contact_id:
        contact_id = data.get("meta", {}).get("sender", {}).get("id")
    if not contact_id and data.get("conversation"):
        contact_id = data.get("conversation", {}).get("contact_id")

    # Extract latest_message_id for incremental capping (bracket the summary)
    latest_message_id = None
    conv = data.get("conversation", {})
    if conv:
        # Check direct field or nested last_message object
        latest_message_id = conv.get("last_message_id") or conv.get("last_message", {}).get("id")

    if not latest_message_id and data.get("messages"):
        msgs = data.get("messages", [])
        if msgs:
            latest_message_id = msgs[-1].get("id")

    if status != "resolved":
        return

    async with AsyncSessionLocal() as db:
        tenant_id = await _resolve_tenant_id(db, alias)
        if not tenant_id:
            return

        # Bulletproof account_id resolution: check DB if missing from webhook
        if not account_id:
            from app.models.integration import IntegrationConfig
            stmt_config = select(IntegrationConfig.account_id).where(
                IntegrationConfig.tenant_id == tenant_id,
                IntegrationConfig.service_name == "chatwoot"
            )
            res = await db.execute(stmt_config)
            account_id = res.scalars().first()

        if not account_id or not conversation_id:
            Log.warning(f"Could not extract account_id ({account_id}) or conversation_id ({conversation_id}) from webhook.")
            return

        Log.info(f"Conversation {conversation_id} status changed to '{status}' (Contact: {contact_id}). Triggering summarization.")

        # Resolve Chatwoot Client
        from app.services.chatbot_service import ChatbotService
        chatbot_service = ChatbotService(db)
        client = await chatbot_service._resolve_client(tenant_id)

        # Summarize Logic (Status-based)
        # We pass the status directly to the summarization service to handle the divergent logic
        from app.services.summarization.service import SummarizationService
        sum_service = SummarizationService(db, client)
        await sum_service.summarize_conversation(
            tenant_id,
            account_id,
            conversation_id,
            status=status,
            contact_id=contact_id,
            latest_message_id=latest_message_id
        )

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

    # 3. Handle Status Change (Summarization)
    elif event == "conversation_status_changed":
        background_tasks.add_task(process_webhook_status_change, webhook_data, alias)

    return {"status": "ok"}