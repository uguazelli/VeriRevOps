from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy import select
from src.core.db import get_session
from src.core.models import GlobalConfig, ChatMessage
from src.core.schemas import (
    RagRequest, RagResponse, LlmRequest, LlmResponse,
    TranscribeUrlRequest, AnalyzeImageUrlRequest,
    ChatMessageCreate, ChatMessageUpdate, ChatMessageResponse,
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


# --- Chat Messages CRUD ---

@router.post("/chat_messages", response_model=ChatMessageResponse)
async def create_chat_message(
    message_data: ChatMessageCreate,
    username: str = Depends(require_auth)
):
    """
    Save a processed individual chat message.
    """
    async with get_session() as db:
        new_message = ChatMessage(**message_data.model_dump())
        db.add(new_message)
        await db.commit()
        await db.refresh(new_message)
        return new_message

@router.get("/chat_messages", response_model=List[ChatMessageResponse])
async def list_chat_messages(
    tenant_id: int = None,
    chatwoot_account_id: int = None,
    chatwoot_conversation_id: int = None,
    is_summarized: bool = None,
    username: str = Depends(require_auth)
):
    """
    List individual chat messages with optional filtering.
    """
    async with get_session() as db:
        query = select(ChatMessage)
        if tenant_id:
            query = query.where(ChatMessage.tenant_id == tenant_id)
        if chatwoot_account_id:
            query = query.where(ChatMessage.chatwoot_account_id == chatwoot_account_id)
        if chatwoot_conversation_id:
            query = query.where(ChatMessage.chatwoot_conversation_id == chatwoot_conversation_id)
        if is_summarized is not None:
            query = query.where(ChatMessage.is_summarized == is_summarized)

        # Optional: Order by message_id or created_at if needed
        query = query.order_by(ChatMessage.message_id.asc())

        result = await db.execute(query)
        return result.scalars().all()


@router.put("/chat_messages/{message_id}", response_model=ChatMessageResponse)
async def update_chat_message(
    message_id: int,
    message_update: ChatMessageUpdate,
    username: str = Depends(require_auth)
):
    """
    Update a Chat Message (e.g., mark as summarized).
    NOTE: message_id refers to the primary key id of the chat_messages table, NOT the chatwoot message ID.
    """
    async with get_session() as db:
        result = await db.execute(select(ChatMessage).where(ChatMessage.id == message_id))
        chat_message = result.scalar_one_or_none()
        if not chat_message:
            raise HTTPException(status_code=404, detail="ChatMessage not found")

        update_data = message_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(chat_message, key, value)

        await db.commit()
        await db.refresh(chat_message)
        return chat_message

@router.delete("/chat_messages/{message_id}")
async def delete_chat_message(
    message_id: int,
    username: str = Depends(require_auth)
):
    """
    Delete a Chat Message manually.
    """
    async with get_session() as db:
        result = await db.execute(select(ChatMessage).where(ChatMessage.id == message_id))
        chat_message = result.scalar_one_or_none()
        if not chat_message:
            raise HTTPException(status_code=404, detail="ChatMessage not found")

        await db.delete(chat_message)
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
