from pydantic import BaseModel
from typing import Optional

class ChatwootConfigBase(BaseModel):
    tenant_id: int
    api_url: str
    api_access_token: str
    account_id: int = 1

class ChatwootConfigCreate(ChatwootConfigBase):
    pass

class ChatwootConfigs(ChatwootConfigBase):
    id: int
    tenant_name: Optional[str] = None
