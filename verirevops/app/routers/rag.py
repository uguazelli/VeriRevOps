from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.schemas import RagFileResponse, RagSearchRequest
from app.services.rag.service import RagService

router = APIRouter(prefix="/api/rag", tags=["RAG"])

def get_rag_service(db: AsyncSession = Depends(get_db)) -> RagService:
    return RagService(db)


@router.post("/files")
async def upload_rag_file(
    tenant_id: int = Form(...),
    file: UploadFile = File(...),
    service: RagService = Depends(get_rag_service)
):
    content = (await file.read()).decode("utf-8")
    file_id, num_chunks = await service.ingest_file(tenant_id, file.filename, content)
    return {
        "id": file_id,
        "filename": file.filename,
        "message": f"File uploaded and processed into {num_chunks} chunks."
    }


@router.get("/files/{tenant_id}", response_model=List[RagFileResponse])
async def list_rag_files(tenant_id: int, service: RagService = Depends(get_rag_service)):
    files = await service.list_tenant_files(tenant_id)
    return [{"id": f.id, "filename": f.filename, "uploaded_at": str(f.uploaded_at)} for f in files]


@router.delete("/files/{file_id}")
async def delete_rag_file(file_id: int, service: RagService = Depends(get_rag_service)):
    success = await service.delete_file(file_id)
    if not success:
        raise HTTPException(status_code=404, detail="File not found")
    return {"message": "File deleted"}


@router.post("/search")
async def search_rag(
    request: RagSearchRequest,
    service: RagService = Depends(get_rag_service)
):
    answer = await service.perform_search(request.session_id, request.tenant_id, request.query)
    return {
        "answer": answer,
        "query": request.query
    }
