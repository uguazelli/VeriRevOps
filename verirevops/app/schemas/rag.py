from pydantic import BaseModel
from typing import Optional

class RagFileResponse(BaseModel):
    id: int
    filename: str
    uploaded_at: str

class RagSearchRequest(BaseModel):
    tenant_id: int
    session_id: Optional[int] = 4 # Default to test session if missing
    query: str
    limit: Optional[int] = 5

class RagSearchResponse(BaseModel):
    answer: str
    query: str
