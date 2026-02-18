from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.core.db import get_db
from app.models import RagFile, RagChunk
from app.rag.ingestion import ingest_file_content, embed_query

router = APIRouter(prefix="/api/rag", tags=["RAG"])

# --- Models ---
class RagFileResponse(BaseModel):
    id: int
    filename: str
    uploaded_at: str  # ORM returns datetime, Pydantic handles str conversion often, or use datetime type

class RagSearchRequest(BaseModel):
    tenant_id: int
    query: str
    limit: Optional[int] = 5

class RagSearchResponse(BaseModel):
    content: str
    metadata: dict
    similarity: float

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

@router.post("/search", response_model=List[RagSearchResponse])
async def search_rag(request: RagSearchRequest, session: AsyncSession = Depends(get_db)):
    try:
        # 1. Generate embedding for query
        query_vector = await embed_query(request.query)

        # 2. Search database using pgvector l2_distance
        # Filter chunks by files belonging to the tenant
        # Re-query to get distance for UI percentage
        stmt_with_dist = (
            select(RagChunk, RagChunk.embedding.l2_distance(query_vector).label("distance"))
            .join(RagFile)
            .where(RagFile.tenant_id == request.tenant_id)
            .order_by("distance")
            .limit(request.limit)
        )

        result = await session.execute(stmt_with_dist)
        rows = result.all() # [(RagChunk, distance), ...]

        results = []
        for chunk, distance in rows:
            # Simple conversion: L2 distance isn't 0-1 similarity directly.
            # Using simple inversion for now or assuming small distance = high similarity.

            sim_score = max(0, 1 - distance) # distinct approximation

            results.append(RagSearchResponse(
                content=chunk.content,
                metadata=chunk.chunk_metadata,
                similarity=float(sim_score)
            ))

        return results

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
