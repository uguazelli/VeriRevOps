import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse

from rag.models.schemas import QueryRequest, QueryResponse
from rag.services.rag_service import generate_answer
from rag.services.ingest_service import ingest_document

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """
    Execute a RAG query against the knowledge base.
    """
    try:
        session_id = request.session_id
        if not session_id:
            session_id = uuid.uuid4()

        answer, session_id, context = await generate_answer(
            client_id=request.client_id,
            query=request.query,
            session_id=session_id,
            complexity_score=request.complexity_score,
            pricing_intent=request.pricing_intent,
            external_context=request.external_context,
        )

        return QueryResponse(
            answer=answer,
            session_id=session_id,
            context=context
        )
    except Exception as e:
        logger.error(f"RAG Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest")
async def ingest_file(
    background_tasks: BackgroundTasks,
    client_id: Annotated[int, Form()],
    file: Annotated[UploadFile, File()],
):
    """
    Ingest a file (text or image) into the RAG system.
    """
    if not file.filename.lower().endswith(
        (".txt", ".md", ".jpg", ".jpeg", ".png", ".webp")
    ):
        raise HTTPException(
            status_code=400,
            detail="Supported formats: .txt, .md, .jpg, .png, .webp"
        )

    content_bytes = await file.read()

    try:
        text_content = None
        file_bytes = None

        if file.filename.lower().endswith((".txt", ".md")):
            text_content = content_bytes.decode("utf-8")
        else:
            file_bytes = content_bytes

        background_tasks.add_task(
            ingest_document,
            client_id,
            file.filename,
            content=text_content,
            file_bytes=file_bytes,
        )

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"message": f"Started processing {file.filename}"}
        )
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to process file")
