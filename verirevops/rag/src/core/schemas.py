from pydantic import BaseModel
from uuid import UUID
from typing import Optional, Union

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
    role: str
    message: str

class ChatMessageUpdate(BaseModel):
    is_summarized: Optional[bool] = None

class ChatMessageResponse(BaseModel):
    id: int
    tenant_id: int
    chatwoot_account_id: int
    chatwoot_conversation_id: int
    message_id: int
    role: str
    message: str
    is_summarized: bool

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
