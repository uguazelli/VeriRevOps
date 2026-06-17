from fastapi import APIRouter, Depends, File, Form, UploadFile

from src.core.auth import require_auth
from src.core.models import User
from src.modules.ai.schemas import (
    AnalyzeImageUrlRequest,
    LlmRequest,
    LlmResponse,
    TranscribeUrlRequest,
)
from src.modules.ai.text import get_chat_response
from src.modules.ai.transcription import transcribe_audio
from src.modules.ai.vision import analyze_image
from src.modules.media import download_file_from_url


router = APIRouter()


@router.post("/llm", response_model=LlmResponse)
async def api_llm(request: LlmRequest, user: User = Depends(require_auth)):
    answer = await get_chat_response(request.message, provider=request.provider)
    return LlmResponse(answer=answer)


@router.post("/transcribe")
async def api_transcribe(
    file: UploadFile = File(...),
    provider: str = Form("gemini"),
    user: User = Depends(require_auth),
):
    content = await file.read()
    text = await transcribe_audio(content, file.filename, provider)
    return {"text": text}


@router.post("/transcribe-url")
async def api_transcribe_url(
    request: TranscribeUrlRequest,
    user: User = Depends(require_auth),
):
    content, filename = await download_file_from_url(request.url)
    text = await transcribe_audio(content, filename, request.provider)
    return {"text": text}


@router.post("/analyze-image")
async def api_analyze_image(
    file: UploadFile = File(...),
    prompt: str = Form("Describe this image in detail."),
    provider: str = Form("gemini"),
    user: User = Depends(require_auth),
):
    content = await file.read()
    answer = await analyze_image(content, file.filename, prompt, provider)
    return {"answer": answer}


@router.post("/analyze-image-url")
async def api_analyze_image_url(
    request: AnalyzeImageUrlRequest,
    user: User = Depends(require_auth),
):
    content, filename = await download_file_from_url(request.url)
    answer = await analyze_image(content, filename, request.prompt, request.provider)
    return {"answer": answer}
