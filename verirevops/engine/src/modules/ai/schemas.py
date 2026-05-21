from pydantic import BaseModel


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
