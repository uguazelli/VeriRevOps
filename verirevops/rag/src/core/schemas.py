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

class ChatSessionCreate(BaseModel):
    tenant_id: int
    chatwoot_account_id: int
    chatwoot_conversation_id: int
    last_summarized_message_id: int = 0
    last_private_summarized_message_id: int = 0

class ChatSessionUpdate(BaseModel):
    last_summarized_message_id: Optional[int] = None
    last_private_summarized_message_id: Optional[int] = None

class ChatSessionResponse(BaseModel):
    id: int
    tenant_id: int
    chatwoot_account_id: int
    chatwoot_conversation_id: int
    last_summarized_message_id: int
    last_private_summarized_message_id: int

    class Config:
        from_attributes = True
