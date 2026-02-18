from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Body
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.db import get_db
from app.models import RagFile, RagChunk
from app.rag.ingestion import ingest_file_content, embed_query
from app.schemas import RagFileResponse, RagSearchRequest
from app.core.logger import Log

router = APIRouter(prefix="/api/rag", tags=["RAG"])

# --- Routes ---

@router.post("/files")
async def upload_rag_file(
    tenant_id: int = Form(...),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db)
):
    try:
        # 1. Register the file
        new_file = RagFile(tenant_id=tenant_id, filename=file.filename)
        session.add(new_file)
        await session.commit()
        await session.refresh(new_file)

        # 2. Process file content
        content = (await file.read()).decode("utf-8")

        # 3. Ingest (Chunk & Embed)
        # Pass session to ingestion function
        num_chunks = await ingest_file_content(session, new_file.id, content)

        return {
            "id": new_file.id,
            "filename": new_file.filename,
            "message": f"File uploaded and processed into {num_chunks} chunks."
        }
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/files/{tenant_id}", response_model=List[RagFileResponse])
async def list_rag_files(tenant_id: int, session: AsyncSession = Depends(get_db)):
    try:
        stmt = select(RagFile).where(RagFile.tenant_id == tenant_id).order_by(RagFile.uploaded_at.desc())
        result = await session.execute(stmt)
        files = result.scalars().all()

        # Convert datetime to string for simple JSON response if needed,
        # but FastApi/Pydantic can handle datetime objects.
        # However, to match previous manual SQL formatting, let's return objects.
        return [{"id": f.id, "filename": f.filename, "uploaded_at": str(f.uploaded_at)} for f in files]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/files/{file_id}")
async def delete_rag_file(file_id: int, session: AsyncSession = Depends(get_db)):
    try:
        # Check if file exists
        file = await session.get(RagFile, file_id)
        if not file:
             raise HTTPException(status_code=404, detail="File not found")

        # Delete (Chunks are cascaded by DB usually, ORM can handle it too)
        await session.delete(file)
        await session.commit()

        return {"message": "File deleted"}
    except HTTPException as e:
        raise e
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/search")
async def search_rag(
    request: RagSearchRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        # Import only inside function to avoid circular imports if any,
        # but top-level is fine usually.
        from app.rag.retrieve import invoke_rag_graph

        # Verify session exists (optional but good practice)
        # For now, just pass it through. If it doesn't exist, history will be empty.

        answer = await invoke_rag_graph(request.session_id, request.query, db, request.tenant_id)

        return {
            "answer": answer,
            # We could return sources here too if we modified invoke_rag_graph to return state
            "query": request.query
        }

    except Exception as e:
        Log.error(f"Error in RAG Search: {e}")
        raise HTTPException(status_code=400, detail=str(e))
