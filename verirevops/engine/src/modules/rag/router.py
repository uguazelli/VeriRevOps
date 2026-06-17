from fastapi import APIRouter, Depends, HTTPException

from src.core.auth import require_auth
from src.core.models import User
from src.modules.rag.schemas import RagRequest, RagResponse
from src.modules.rag.service import generate_answer


router = APIRouter()


@router.post("/rag", response_model=RagResponse)
async def api_rag(request: RagRequest, user: User = Depends(require_auth)):
    if user.role != "superadmin" and user.tenant_id != request.tenant_id:
        raise HTTPException(status_code=403, detail="Access denied to this tenant")
    answer = await generate_answer(request.tenant_id, request.message, provider=request.provider)
    return RagResponse(answer=answer)
