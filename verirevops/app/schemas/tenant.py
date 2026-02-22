from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class TenantBase(BaseModel):
    name: str
    slug: str
    url: str
    custom_prompt: Optional[str] = None
    languages: Optional[str] = None
    is_active: bool = True

class TenantCreate(TenantBase):
    pass

class Tenants(TenantBase):
    id: int

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
