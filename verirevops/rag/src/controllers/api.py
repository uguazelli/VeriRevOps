from fastapi import APIRouter, Depends, UploadFile, File, Form
from uuid import UUID
from src.core.schemas import QueryRequest, QueryResponse
from src.core.auth import require_auth
from src.services.rag import generate_answer
from src.services.transcription import transcribe_audio

router = APIRouter()

@router.post("/query", response_model=QueryResponse)
async def api_query_rag(
    request: QueryRequest,
    username: str = Depends(require_auth)
):
    answer, requires_human = generate_answer(
        request.tenant_id,
        request.query,
        use_hyde=request.use_hyde,
        use_rerank=request.use_rerank,
        provider=request.provider
    )
    return QueryResponse(
        answer=answer,
        requires_human=requires_human
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
