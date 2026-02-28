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
