from pydantic import BaseModel

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

class TranscribeUrlRequest(BaseModel):
    url: str
    provider: str = "gemini"

class AnalyzeImageUrlRequest(BaseModel):
    url: str
    prompt: str = "Describe this image in detail."
    provider: str = "gemini"
