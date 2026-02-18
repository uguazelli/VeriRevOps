from fastapi import APIRouter, Body, Depends, BackgroundTasks
from app.core.db import AsyncSessionLocal
from app.services.chatbot_service import ChatbotService
from app.core.logger import Log

router = APIRouter(
    prefix="/api",
    tags=["chatwoot"]
)

async def process_webhook_message(data: dict, alias: str):
    """Background task to process the webhook via ChatbotService."""
    message_type = data.get("message_type")
    private = data.get("private", False)

    if message_type != "incoming" or private:
        return

    async with AsyncSessionLocal() as db:
        service = ChatbotService(db)
        await service.process_webhook_message(data, alias)

@router.post("/webhook/{alias}")
async def handle_webhook(
    alias: str,
    background_tasks: BackgroundTasks,
    webhook_data: dict = Body(...)
):
    background_tasks.add_task(process_webhook_message, webhook_data, alias)
    return {"status": "ok"}