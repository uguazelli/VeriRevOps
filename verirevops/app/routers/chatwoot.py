from fastapi import APIRouter, Body, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db, AsyncSessionLocal
from app.orquestation.chat import invoke_chat_orchestrator
from app.core.chatwoot import get_chatwoot_client, ChatwootClient
from app.models import Tenant, ChatwootConfig
from sqlalchemy import select

router = APIRouter(
    prefix="/api",
    tags=["chatwoot"]
)

async def process_webhook_message(data: dict, alias: str):
    print(f"Processing webhook task for data: {data}", flush=True)
    event = data.get("event")
    msg_data = data.get("content", {})

    if event != "message_created":
        print(f"Ignored event: {event}", flush=True)
        return

    message_type = data.get("message_type")
    private = data.get("private", False)

    if message_type != "incoming" or private:
        print(f"Ignored message type: {message_type}, private: {private}", flush=True)
        return

    content = data.get("content")
    if not content:
        print("No content", flush=True)
        return

    account_id = data.get("account", {}).get("id")
    conversation_id = data.get("conversation", {}).get("id")

    if not account_id or not conversation_id:
        print("Missing account or conversation ID in webhook", flush=True)
        return

    print(f"Invoking Orchestrator for Account {account_id}, Session {conversation_id}", flush=True)

    async with AsyncSessionLocal() as db:
        try:
            # 1. Resolve Tenant from Alias
            stmt = select(Tenant).where(Tenant.slug == alias)
            result = await db.execute(stmt)
            tenant = result.scalars().first()

            if not tenant:
                print(f"Tenant not found for alias: {alias}", flush=True)
                return

            tenant_id = tenant.id

            ai_response = await invoke_chat_orchestrator(tenant_id, conversation_id, content, db)
            print(f"Orchestrator Response: {ai_response}", flush=True)

            if ai_response:
                # 2. Fetch Chatwoot Config for Tenant
                stmt_config = select(ChatwootConfig).where(ChatwootConfig.tenant_id == tenant_id)
                result_config = await db.execute(stmt_config)
                config = result_config.scalars().first()

                client = None
                if config:
                    client = ChatwootClient(base_url=config.api_url, api_token=config.api_access_token)
                    # Use account_id from config if needed, or from webhook.
                    # Usually webhook has the correct account_id, but if we need to enforce:
                    # account_id = config.account_id
                else:
                    # Fallback to env vars (for backward compatibility/default)
                    client = get_chatwoot_client()

                if client:
                    await client.send_message(account_id, conversation_id, ai_response)
                else:
                    print(f"Chatwoot client not configured for Tenant {tenant_id}, skipping send.", flush=True)
        except Exception as e:
            print(f"Error processing webhook message: {e}", flush=True)
            import traceback
            traceback.print_exc()


@router.post("/webhook/{alias}")
async def handle_webhook(
    alias: str,
    background_tasks: BackgroundTasks,
    webhook_data: dict = Body(...)
):
    background_tasks.add_task(process_webhook_message, webhook_data, alias)
    return {"status": "ok"}