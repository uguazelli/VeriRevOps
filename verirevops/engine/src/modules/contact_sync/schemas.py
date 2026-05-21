from typing import Any

from pydantic import BaseModel, Field
from sqlmodel import SQLModel

from src.core.models import ContactMappingBase


class NormalizedContact(BaseModel):
    chatwoot_contact_id: int
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    company_name: str | None = None
    source_payload: dict[str, Any] = Field(default_factory=dict)


class ContactSyncResult(BaseModel):
    tenant_id: int
    chatwoot_contact_id: int
    service_name: str
    external_id: str
    action: str


class ContactMappingUpdate(SQLModel):
    tenant_id: int
    service_name: str
    external_id: str


class ContactMappingResponse(ContactMappingBase):
    id: int
