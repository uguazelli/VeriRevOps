from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# --- Tenants ---
class TenantBase(BaseModel):
    name: str
    slug: str
    url: str
    is_active: bool = True

class TenantCreate(TenantBase):
    pass

class Tenants(TenantBase):
    id: int

# --- Subscriptions ---
class SubscriptionBase(BaseModel):
    tenant_id: int
    quota_limit: int
    usage_count: int = 0
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class SubscriptionCreate(SubscriptionBase):
    pass

class Subscriptions(SubscriptionBase):
    id: int
    tenant_name: Optional[str] = None

# --- Chat Sessions ---
class ChatSessionCreate(BaseModel):
    tenant_id: int

class ChatSessions(BaseModel):
    id: int
    tenant_id: int
    created_at: datetime
    tenant_name: Optional[str] = None

# --- Chat Messages ---
class ChatMessages(BaseModel):
    id: int
    session_id: int
    content: str
    role: str
    created_at: datetime
    tenant_name: Optional[str] = None
