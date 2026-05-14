from fastapi import APIRouter

from src.modules.contact_sync.models import ContactSyncResult
from src.modules.contact_sync.service import sync_chatwoot_contact_payload_to_crm


router = APIRouter()


@router.post("/contact-sync/chatwoot/{slug}", response_model=ContactSyncResult)
async def sync_chatwoot_contact(
    slug: str,
    payload: dict,
    service_name: str = "espocrm",
):
    """
    Sync one Chatwoot contact payload to the configured CRM.
    """
    return await sync_chatwoot_contact_payload_to_crm(
        slug,
        payload,
        service_name=service_name,
    )

