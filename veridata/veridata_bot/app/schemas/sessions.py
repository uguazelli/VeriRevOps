from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime

class ConversationSessionBase(BaseModel):
    client_id: int
    platform: str = Field(..., max_length=50)
    user_identifier: str = Field(..., max_length=100)
    rag_session_id: Optional[str] = Field(None, max_length=100)

class ConversationSessionCreate(ConversationSessionBase):
    pass

class ConversationSessionRead(ConversationSessionBase):
    id: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
