from fastapi import APIRouter

from src.core.schemas import RagRequest, RagResponse
from src.modules.rag.service import generate_answer


router = APIRouter()


@router.post("/rag", response_model=RagResponse)
async def api_rag(request: RagRequest):
    answer = await generate_answer(
        request.tenant_id,
        request.message,
        provider=request.provider,
    )
    return RagResponse(answer=answer)
