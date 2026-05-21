from fastapi import APIRouter, BackgroundTasks

from src.modules.chatwoot.message_tracking import (
    svc_list_chat_messages,
    svc_upsert_chat_message,
)
from src.modules.chatwoot.schemas import ChatMessageCreate, ChatMessageResponse
from src.modules.chatwoot.service import process_chatwoot_webhook

router = APIRouter()

@router.post("/chatwoot/webhook/{slug}")
async def chatwoot_webhook(
    slug: str,
    payload: dict,
    background_tasks: BackgroundTasks
):
    """
    Endpoint to receive webhooks from Chatwoot.
    """
    background_tasks.add_task(process_chatwoot_webhook, slug, payload)

    return { "status": "accepted" }


@router.post("/chat_messages", response_model=ChatMessageResponse)
async def upsert_chat_message(message_data: ChatMessageCreate):
    """
    Save or update the last summarized message for a conversation.
    """
    return await svc_upsert_chat_message(message_data)


@router.get("/chat_messages", response_model=list[ChatMessageResponse])
async def list_chat_messages(
    tenant_id: int = None,
    chatwoot_account_id: int = None,
    chatwoot_conversation_id: int = None,
):
    """
    List Chatwoot tracking records with optional filtering.
    """
    return await svc_list_chat_messages(
        tenant_id,
        chatwoot_account_id,
        chatwoot_conversation_id,
    )
