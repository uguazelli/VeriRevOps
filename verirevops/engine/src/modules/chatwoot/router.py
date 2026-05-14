from fastapi import APIRouter, BackgroundTasks
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
