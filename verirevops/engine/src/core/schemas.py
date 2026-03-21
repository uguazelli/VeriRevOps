from pydantic import BaseModel
from uuid import UUID
from typing import Optional, Union, List, Dict
from datetime import datetime

class RagRequest(BaseModel):
    tenant_id: int
    message: str
    provider: str = "gemini"

class RagResponse(BaseModel):
    answer: str

class LlmRequest(BaseModel):
    message: str
    provider: str = "gemini"

class LlmResponse(BaseModel):
    answer: str

class TranscribeUrlRequest(BaseModel):
    url: str
    provider: str = "gemini"

class AnalyzeImageUrlRequest(BaseModel):
    url: str
    prompt: str = "Describe this image in detail."
    provider: str = "gemini"



class ChatMessageCreate(BaseModel):
    tenant_id: int
    chatwoot_account_id: int
    chatwoot_conversation_id: int
    message_id: int

class ChatMessageResponse(BaseModel):
    id: int
    tenant_id: int
    chatwoot_account_id: int
    chatwoot_conversation_id: int
    message_id: int

    class Config:
        from_attributes = True

class GlobalConfigCreate(BaseModel):
    settings: dict

class GlobalConfigUpdate(BaseModel):
    settings: dict

class GlobalConfigResponse(BaseModel):
    id: int
    settings: Optional[dict] = None

    class Config:
        from_attributes = True

class ServiceResponse(BaseModel):
    id: int
    tenant_id: int
    name: str
    url: Optional[str] = None
    api_key: Optional[str] = None
    account_id: Optional[str] = None
    settings: Optional[dict] = None

    class Config:
        from_attributes = True

class SubscriptionResponse(BaseModel):
    id: int
    tenant_id: int
    is_active: bool
    quota_limit: int
    usage_count: int
    start_dat: datetime
    end_date: datetime

    class Config:
        from_attributes = True

class ConfigurationResponse(BaseModel):
    id: int
    tenant_id: int
    settings: Optional[dict] = None

    class Config:
        from_attributes = True

class TenantResponse(BaseModel):
    id: int
    slug: str
    created_at: datetime
    services: Dict[str, ServiceResponse] = {}
    subscription: Optional[SubscriptionResponse] = None
    configuration: Optional[ConfigurationResponse] = None

    class Config:
        from_attributes = True

class TenantFullResponse(BaseModel):
    tenant: TenantResponse
    global_config: Optional[GlobalConfigResponse] = None
