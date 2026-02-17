from typing import Optional, Union, List, Dict
from uuid import UUID
from pydantic import BaseModel


class QueryRequest(BaseModel):
    client_id: int
    query: str
    provider: Optional[str] = None
    session_id: Optional[UUID] = None
    complexity_score: Optional[int] = 5
    pricing_intent: Optional[bool] = False
    external_context: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    session_id: Optional[UUID] = None
    context: Optional[str] = None


class SummarizeRequest(BaseModel):
    client_id: int
    session_id: UUID
    provider: Optional[str] = None


class ConversationSummary(BaseModel):
    purchase_intent: str  # High, Medium, Low, None
    urgency_level: str  # Urgent, Normal, Low
    sentiment_score: str  # Positive, Neutral, Negative
    detected_budget: Optional[Union[str, int, float]] = None
    ai_summary: str
    contact_info: Optional[Dict] = {}  # phone, email, name, address, industry
    client_description: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    content: str
    created_at: Optional[str] = None


class ChatHistoryResponse(BaseModel):
    messages: List[ChatMessage]


class AppendMessageRequest(BaseModel):
    role: str
    content: str


class CreateSessionRequest(BaseModel):
    client_id: int


class CreateSessionResponse(BaseModel):
    session_id: UUID
