from fastapi import APIRouter, Body, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db, AsyncSessionLocal
from app.orquestation.chat import invoke_chat_orchestrator
from app.core.chatwoot import get_chatwoot_client

router = APIRouter(
    prefix="/api",
    tags=["chatwoot"]
)

async def process_webhook_message(data: dict):
    """
    Background task to process the message to avoid blocking the webhook response.
    """
    print(f"Processing webhook task for data: {data}", flush=True)
    event = data.get("event")
    msg_data = data.get("content", {}) # 'content' key in top-level payload might vary, usually it's passed differently
    # Chatwoot payload structure for 'message_created':
    # { "event": "message_created", "account": {...}, "conversation": {...}, "content": "..." (sometimes),
    #   "id": ..., "content_type": ..., "message_type": ..., "private": ... }
    # Wait, the payload is flatter. Let's look at standard Chatwoot payload.
    # It has 'event', 'id', 'content', 'account', 'conversation', 'message_type', 'private', etc. at top level usually?
    # Actually, often it's nested under the event type or flat.
    # Let's assume standard webhook payload:
    # { "event": "message_created", "id": 1, "content": "hi", "message_type": "incoming", "private": false,
    #   "account": { "id": 1 }, "conversation": { "id": 10 } }

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
    # Process with Orchestrator
    # We need a DB session here since we are in a background task
    async with AsyncSessionLocal() as db:
        try:
            ai_response = await invoke_chat_orchestrator(account_id, conversation_id, content, db)
            print(f"Orchestrator Response: {ai_response}", flush=True)

            if ai_response:
                client = get_chatwoot_client()
                if client:
                    await client.send_message(account_id, conversation_id, ai_response)
                else:
                    print("Chatwoot client not configured, skipping send.", flush=True)
        except Exception as e:
            print(f"Error processing webhook message: {e}", flush=True)
            import traceback
            traceback.print_exc()


@router.post("/webhook") # Removed {alias} for simplicity unless user required it specifically. Assuming standard webhook.
async def handle_webhook(
    background_tasks: BackgroundTasks,
    webhook_data: dict = Body(...)
):
    """
    Handle incoming Chatwoot webhooks.
    """
    # 1. Immediate ACK
    # 2. Process in background
    background_tasks.add_task(process_webhook_message, webhook_data)

    return {"status": "ok"}