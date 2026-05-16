from fastapi import APIRouter, BackgroundTasks

from src.modules.conversation_summary.service import process_conversation_summary_webhook


router = APIRouter()


@router.post("/conversation-summary/chatwoot/{slug}")
async def summarize_chatwoot_conversation(
    slug: str,
    payload: dict,
    background_tasks: BackgroundTasks,
    service_name: str = "espocrm",
):
    """
    Accept Chatwoot resolved-conversation webhooks and summarize in the background.
    """
    background_tasks.add_task(
        process_conversation_summary_webhook,
        slug,
        payload,
        service_name,
    )

    return {"status": "accepted"}
