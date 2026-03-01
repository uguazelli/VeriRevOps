from fastapi import APIRouter, Depends, UploadFile, File, Form
from src.core.schemas import RagRequest, RagResponse, LlmRequest, LlmResponse
from src.core.auth import require_auth
from src.services.rag import generate_answer
from src.services.transcription import transcribe_audio
from src.services.llm import get_chat_response

router = APIRouter()

@router.post("/rag", response_model=RagResponse)
async def api_rag(
    request: RagRequest,
    username: str = Depends(require_auth)
):
    answer = await generate_answer(
        request.tenant_id,
        request.message,
        provider=request.provider
    )
    return RagResponse(
        answer=answer
    )


@router.post("/transcribe")
async def api_transcribe(
    file: UploadFile = File(...),
    provider: str = Form("gemini"),
    username: str = Depends(require_auth)
):
    """
    Transcribes uploaded audio file.
    """
    content = await file.read()
    text = await transcribe_audio(content, file.filename, provider)

    return {"text": text}


@router.post("/llm", response_model=LlmResponse)
async def api_llm(
    request: LlmRequest,
    username: str = Depends(require_auth)
):
    """
    Direct endpoint to query LLM without RAG.
    """
    answer = await get_chat_response(
        request.message,
        provider=request.provider
    )
    return LlmResponse(answer=answer)
