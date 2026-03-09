from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy import select
from src.core.db import get_session
from src.core.models import ChatSession, GlobalConfig
from src.core.schemas import (
    RagRequest, RagResponse, LlmRequest, LlmResponse,
    TranscribeUrlRequest, AnalyzeImageUrlRequest,
    ChatSessionCreate, ChatSessionUpdate, ChatSessionResponse,
    GlobalConfigCreate, GlobalConfigUpdate, GlobalConfigResponse
)
from src.core.auth import require_auth
from src.services.rag import generate_answer
from src.services.transcription import transcribe_audio
from src.services.llm import get_chat_response
from src.services.image_analysis import analyze_image
from src.services.media_downloader import download_file_from_url

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


@router.post("/transcribe-url")
async def api_transcribe_url(
    request: TranscribeUrlRequest,
    username: str = Depends(require_auth)
):
    """
    Downloads audio from URL and transcribes it.
    """
    content, filename = await download_file_from_url(request.url)
    text = await transcribe_audio(content, filename, request.provider)

    return {"text": text}


@router.post("/analyze-image")
async def api_analyze_image(
    file: UploadFile = File(...),
    prompt: str = Form("Describe this image in detail."),
    provider: str = Form("gemini"),
    username: str = Depends(require_auth)
):
    """
    Analyzes uploaded image using the specified LLM.
    """
    content = await file.read()
    answer = await analyze_image(content, file.filename, prompt, provider)

    return {"answer": answer}


@router.post("/analyze-image-url")
async def api_analyze_image_url(
    request: AnalyzeImageUrlRequest,
    username: str = Depends(require_auth)
):
    """
    Downloads image from URL and analyzes it using the specified LLM.
    """
    content, filename = await download_file_from_url(request.url)
    answer = await analyze_image(content, filename, request.prompt, request.provider)

    return {"answer": answer}


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


# --- Chat Session CRUD ---

@router.post("/chat_sessions", response_model=ChatSessionResponse)
async def upsert_chat_session(
    session_data: ChatSessionCreate,
    username: str = Depends(require_auth)
):
    """
    Create or update a Chat Session checkpoint for summarization.
    """
    async with get_session() as db:
        # Check if the session already exists
        query = select(ChatSession).where(
            ChatSession.tenant_id == session_data.tenant_id,
            ChatSession.chatwoot_account_id == session_data.chatwoot_account_id,
            ChatSession.chatwoot_conversation_id == session_data.chatwoot_conversation_id
        )
        result = await db.execute(query)
        existing_session = result.scalar_one_or_none()

        if existing_session:
            # Update existing
            if session_data.last_summarized_message_id is not None:
                existing_session.last_summarized_message_id = session_data.last_summarized_message_id
            if session_data.last_private_summarized_message_id is not None:
                existing_session.last_private_summarized_message_id = session_data.last_private_summarized_message_id
            session_to_return = existing_session
        else:
            # Create new
            new_session = ChatSession(**session_data.model_dump())
            db.add(new_session)
            session_to_return = new_session

        await db.commit()
        await db.refresh(session_to_return)
        return session_to_return

@router.get("/chat_sessions", response_model=List[ChatSessionResponse])
async def list_chat_sessions(
    tenant_id: int = None,
    chatwoot_account_id: int = None,
    chatwoot_conversation_id: int = None,
    username: str = Depends(require_auth)
):
    """
    List Chat Sessions with optional filtering.
    """
    async with get_session() as db:
        query = select(ChatSession)
        if tenant_id:
            query = query.where(ChatSession.tenant_id == tenant_id)
        if chatwoot_account_id:
            query = query.where(ChatSession.chatwoot_account_id == chatwoot_account_id)
        if chatwoot_conversation_id:
            query = query.where(ChatSession.chatwoot_conversation_id == chatwoot_conversation_id)

        result = await db.execute(query)
        return result.scalars().all()

@router.get("/chat_sessions/{session_id}", response_model=ChatSessionResponse)
async def get_chat_session(
    session_id: int,
    username: str = Depends(require_auth)
):
    """
    Get a specific Chat Session by ID.
    """
    async with get_session() as db:
        result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
        chat_session = result.scalar_one_or_none()
        if not chat_session:
            raise HTTPException(status_code=404, detail="ChatSession not found")
        return chat_session

@router.put("/chat_sessions/{session_id}", response_model=ChatSessionResponse)
async def update_chat_session(
    session_id: int,
    session_update: ChatSessionUpdate,
    username: str = Depends(require_auth)
):
    """
    Update a Chat Session's last summarized message IDs.
    """
    async with get_session() as db:
        result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
        chat_session = result.scalar_one_or_none()
        if not chat_session:
            raise HTTPException(status_code=404, detail="ChatSession not found")

        update_data = session_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(chat_session, key, value)

        await db.commit()
        await db.refresh(chat_session)
        return chat_session

@router.delete("/chat_sessions/{session_id}")
async def delete_chat_session(
    session_id: int,
    username: str = Depends(require_auth)
):
    """
    Delete a Chat Session.
    """
    async with get_session() as db:
        result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
        chat_session = result.scalar_one_or_none()
        if not chat_session:
            raise HTTPException(status_code=404, detail="ChatSession not found")

        await db.delete(chat_session)
        await db.commit()
        return {"ok": True}


# --- Global Config CRUD ---

@router.get("/global_configs", response_model=GlobalConfigResponse)
async def get_global_config(username: str = Depends(require_auth)):
    """
    Get the global configuration (assumes single row with id=1).
    """
    async with get_session() as db:
        result = await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))
        config = result.scalar_one_or_none()
        if not config:
            raise HTTPException(status_code=404, detail="Global config not found")
        return config

@router.post("/global_configs", response_model=GlobalConfigResponse)
async def upsert_global_config(
    config_data: GlobalConfigCreate,
    username: str = Depends(require_auth)
):
    """
    Upsert the single global configuration (id=1).
    """
    async with get_session() as db:
        result = await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))
        config = result.scalar_one_or_none()

        if config:
            config.settings = config_data.settings
        else:
            # First row gets forced to ID 1
            config = GlobalConfig(id=1, settings=config_data.settings)
            db.add(config)

        await db.commit()
        await db.refresh(config)
        return config
