from pydantic import BaseModel


class RagRequest(BaseModel):
    tenant_id: int
    message: str
    provider: str = "gemini"


class RagResponse(BaseModel):
    answer: str
