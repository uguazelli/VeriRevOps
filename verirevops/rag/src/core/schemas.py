from pydantic import BaseModel
from uuid import UUID
from typing import Optional, Union

class QueryRequest(BaseModel):
    tenant_id: int
    query: str
    use_hyde: bool = False
    use_rerank: bool = False
    provider: str = "gemini"

class QueryResponse(BaseModel):
    answer: str
    requires_human: bool = False

class ChatRequest(BaseModel):
    message: str
    provider: str = "gemini"

class ChatResponse(BaseModel):
    answer: str
