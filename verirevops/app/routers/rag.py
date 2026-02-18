from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from typing import List, Optional
from pydantic import BaseModel
from app.models import RagFileResponse, RagSearchRequest, RagSearchResponse
from app.core.database import execute_read_query, execute_write_query
from app.core.queries import (
    GET_RAG_FILES_BY_TENANT, INSERT_RAG_FILE, DELETE_RAG_FILE,
    SEARCH_SIMILAR_CHUNKS, GET_RAG_FILE_BY_ID, INSERT_RAG_CHUNK, DELETE_CHUNKS_BY_FILE
)

router = APIRouter(
    prefix="/api/rag",
    tags=["rag"]
)

@router.get("/files/{tenant_id}", response_model=List[RagFileResponse])
async def list_rag_files(tenant_id: int):
    try:
        rows = execute_read_query(GET_RAG_FILES_BY_TENANT, (tenant_id,))
        files = []
        for row in rows:
            files.append(RagFileResponse(
                id=row[0],
                filename=row[1],
                uploaded_at=str(row[2])
            ))
        return files
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/files")
async def upload_rag_file(tenant_id: int = Form(...), file: UploadFile = File(...)):
    try:
        # 1. Register the file
        file_id = execute_write_query(INSERT_RAG_FILE, (tenant_id, file.filename))[0]

        # 2. Process file content (Placeholder logic for now)
        # In a real implementation, we would read the file, chunk it, embed it, and insert chunks.
        # content = await file.read()
        # For now, we just acknowledge the upload.

        return {"id": file_id, "filename": file.filename, "message": "File uploaded successfully (processing pending)"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/files/{file_id}")
async def delete_rag_file(file_id: int):
    try:
        # Check if file exists
        rows = execute_read_query(GET_RAG_FILE_BY_ID, (file_id,))
        if not rows:
            raise HTTPException(status_code=404, detail="File not found")

        # Delete chunks (cascade usually handles this, but good to be explicit or if cascade key missing)
        # Our table definition has ON DELETE CASCADE, so deleting the file is enough.

        rowcount = execute_write_query(DELETE_RAG_FILE, (file_id,))
        if rowcount == 0:
             raise HTTPException(status_code=404, detail="File not found")

        return {"message": "File deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
         raise HTTPException(status_code=400, detail=str(e))

@router.post("/search", response_model=List[RagSearchResponse])
async def search_rag(request: RagSearchRequest):
    try:
        # This requires generating an embedding for the query.
        # Since we don't have the embedding model integrated here yet, we can't run the actual SQL query
        # because it expects a vector param.
        # For now, we will return a mock response or require the embedding to be passed (which isn't ideal for frontend).

        # PROPOSAL: We leave this endpoint as a placeholder until the embedding logic is added in the next steps.
        # Or we can accept 'embedding' in the request for testing if the user wants.

        # For this step, I will simplify and just return an empty list or mock to show structure,
        # acknowledging that the vector generation is the next logical dependency.

        return []

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
