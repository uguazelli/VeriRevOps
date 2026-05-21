from sqlmodel import SQLModel

from src.core.models import ChatMessageBase


class ChatMessageCreate(SQLModel):
    tenant_id: int
    chatwoot_account_id: int
    chatwoot_conversation_id: int
    message_id: int


class ChatMessageResponse(ChatMessageBase):
    id: int
