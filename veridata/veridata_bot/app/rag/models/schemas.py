[
    {"StartLine": 2, "EndLine": 2, "TargetContent": "from uuid import UUID", "ReplacementContent": "from uuid import UUID\nfrom typing import Optional, Union", "AllowMultiple": False},
    {"StartLine": 6, "EndLine": 13, "TargetContent": "class QueryRequest(BaseModel):\n    tenant_id: UUID\n    query: str\n    provider: Optional[str] = None\n    session_id: Optional[UUID] = None\n    complexity_score: Optional[int] = 5\n    pricing_intent: Optional[bool] = False\n    external_context: Optional[str] = None", "ReplacementContent": "class QueryRequest(BaseModel):\n    client_id: int\n    query: str\n    provider: Optional[str] = None\n    session_id: Optional[UUID] = None\n    complexity_score: Optional[int] = 5\n    pricing_intent: Optional[bool] = False\n    external_context: Optional[str] = None", "AllowMultiple": False},
    {"StartLine": 22, "EndLine": 26, "TargetContent": "class SummarizeRequest(BaseModel):\n    tenant_id: UUID\n    session_id: UUID\n    provider: Optional[str] = None", "ReplacementContent": "class SummarizeRequest(BaseModel):\n    client_id: int\n    session_id: UUID\n    provider: Optional[str] = None", "AllowMultiple": False},
    {"StartLine": 53, "EndLine": 54, "TargetContent": "class CreateSessionRequest(BaseModel):\n    tenant_id: UUID", "ReplacementContent": "class CreateSessionRequest(BaseModel):\n    client_id: int", "AllowMultiple": False}
]
from uuid import UUID
from typing import Optional, Union
from pydantic import BaseModel

class QueryRequest(BaseModel):
    tenant_id: UUID
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
    tenant_id: UUID
    session_id: UUID
    provider: Optional[str] = None


class ConversationSummary(BaseModel):
    purchase_intent: str  # High, Medium, Low, None
    urgency_level: str  # Urgent, Normal, Low
    sentiment_score: str  # Positive, Neutral, Negative
    detected_budget: Optional[Union[str, int, float]] = None
    ai_summary: str
    contact_info: Optional[dict] = {}  # phone, email, name, address, industry
    client_description: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    content: str
    created_at: Optional[str] = None


class ChatHistoryResponse(BaseModel):
    messages: list[ChatMessage]


class AppendMessageRequest(BaseModel):
    role: str
    content: str


class CreateSessionRequest(BaseModel):
    tenant_id: UUID


class CreateSessionResponse(BaseModel):
    session_id: UUID
