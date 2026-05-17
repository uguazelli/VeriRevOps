from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class NormalizedContact(BaseModel):
    chatwoot_contact_id: int
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    source_payload: Dict[str, Any] = Field(default_factory=dict)


class ContactSyncResult(BaseModel):
    tenant_id: int
    chatwoot_contact_id: int
    service_name: str
    external_id: str
    action: str
