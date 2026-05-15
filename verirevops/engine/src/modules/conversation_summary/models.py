from typing import Optional

from pydantic import BaseModel


class CrmSummaryTarget(BaseModel):
    entity_type: str
    external_id: str
    source: str


class ConversationSummaryResult(BaseModel):
    tenant_id: int
    chatwoot_account_id: int
    chatwoot_conversation_id: int
    after_message_id: int
    latest_message_id: Optional[int] = None
    crm_entity_type: Optional[str] = None
    crm_external_id: Optional[str] = None
    action: str

