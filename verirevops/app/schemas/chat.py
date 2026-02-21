from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ChatSessionCreate(BaseModel):
    tenant_id: int

class ChatSessions(BaseModel):
    id: int
    tenant_id: int
    created_at: datetime
    status: Optional[str] = None
    last_activity_at: Optional[datetime] = None
    tenant_name: Optional[str] = None
