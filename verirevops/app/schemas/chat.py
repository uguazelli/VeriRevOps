from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from typing import Optional, List

class SessionKey(BaseModel):
    tenant_id: int
    account_id: int
    conversation_id: int

    @classmethod
    def from_payload(cls, tenant_id: int, payload: any):
        """Helper to create SessionKey from various Chatwoot payloads."""
        account_id = getattr(payload.account, 'id', None)
        conv_id = getattr(payload.conversation, 'id', None)

        if not account_id or not conv_id:
            # Try direct attributes (some fragments have them at root)
            account_id = account_id or getattr(payload, 'account_id', None)
            conv_id = conv_id or getattr(payload, 'id', None)

        if not account_id or not conv_id:
            return None

        return cls(
            tenant_id=tenant_id,
            account_id=int(account_id),
            conversation_id=int(conv_id)
        )

class OrchestrationInput(BaseModel):
    session_key: SessionKey
    user_message: str
    attachments: Optional[List[dict]] = []
class ChatSessionCreate(BaseModel):
    tenant_id: int

class ChatSessions(BaseModel):
    id: int
    tenant_id: int
    created_at: datetime
    status: Optional[str] = None
    last_activity_at: Optional[datetime] = None
    tenant_name: Optional[str] = None

class ChatwootAccount(BaseModel):
    id: int

class ChatwootConversation(BaseModel):
    id: int
    status: Optional[str] = None
    contact_id: Optional[int] = None
    last_message_id: Optional[int] = None

class ChatwootAttachment(BaseModel):
    file_type: str
    data_url: str
    content_type: Optional[str] = None

class ChatwootMessagePayload(BaseModel):
    content: Optional[str] = ""
    account: Optional[ChatwootAccount] = None
    conversation: Optional[ChatwootConversation] = None
    attachments: Optional[list[ChatwootAttachment]] = []
    message_type: Optional[str] = None
    private: Optional[bool] = False

class ChatwootContactPayload(BaseModel):
    id: int
    email: Optional[str] = None
    name: Optional[str] = None
    phone_number: Optional[str] = None

class ChatwootStatusChangePayload(BaseModel):
    account: Optional[ChatwootAccount] = None
    account_id: Optional[int] = None
    conversation: Optional[ChatwootConversation] = None
    id: Optional[int] = None # Conversation ID
    status: Optional[str] = None
    # Flexible fields for contact and message tracking
    contact_inbox: Optional[dict] = None
    meta: Optional[dict] = None
    messages: Optional[list[dict]] = None
