from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class HealthCheckResponse(BaseModel):
    status: str
    message: str


class TenantCreate(BaseModel):
    name: str
    slug: str
    url: str
    is_active: bool = True

class Tenants(TenantCreate):
    id: int


class SubscriptionCreate(BaseModel):
    tenant_id: int
    quota_limit: int
    usage_count: int = 0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class Subscriptions(SubscriptionCreate):
    id: int
    tenant_name: Optional[str] = None


class ChatSessionCreate(BaseModel):
    tenant_id: int

class ChatSessions(ChatSessionCreate):
    id: int
    created_at: datetime
    tenant_name: Optional[str] = None


class ChatMessages(BaseModel):
    id: int
    session_id: int
    content: str
    role: str
    created_at: datetime
    tenant_name: Optional[str] = None


class RagFileResponse(BaseModel):
    id: int
    filename: str
    uploaded_at: str

class RagSearchRequest(BaseModel):
    tenant_id: int
    query: str
    limit: int = 5

class RagSearchResponse(BaseModel):
    content: str
    metadata: dict
    similarity: float