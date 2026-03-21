from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from src.core.db import get_session
from src.core.models import GlobalConfig, ChatMessage, Tenant
from src.core.schemas import (
    RagRequest, RagResponse, LlmRequest, LlmResponse,
    TranscribeUrlRequest, AnalyzeImageUrlRequest,
    TranscribeUrlRequest, AnalyzeImageUrlRequest,
    ChatMessageCreate, ChatMessageResponse,
    GlobalConfigCreate, GlobalConfigUpdate, GlobalConfigResponse,
    TenantResponse, TenantFullResponse
)
from src.services.rag import generate_answer
from src.services.transcription import transcribe_audio
from src.services.llm import get_chat_response
from src.services.image_analysis import analyze_image
from src.services.media_downloader import download_file_from_url

router = APIRouter()

@router.post("/rag", response_model=RagResponse)
async def api_rag(
    request: RagRequest
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
    provider: str = Form("gemini")
):
    """
    Transcribes uploaded audio file.
    """
    content = await file.read()
    text = await transcribe_audio(content, file.filename, provider)

    return {"text": text}


@router.post("/transcribe-url")
async def api_transcribe_url(
    request: TranscribeUrlRequest
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
    provider: str = Form("gemini")
):
    """
    Analyzes uploaded image using the specified LLM.
    """
    content = await file.read()
    answer = await analyze_image(content, file.filename, prompt, provider)

    return {"answer": answer}


@router.post("/analyze-image-url")
async def api_analyze_image_url(
    request: AnalyzeImageUrlRequest
):
    """
    Downloads image from URL and analyzes it using the specified LLM.
    """
    content, filename = await download_file_from_url(request.url)
    answer = await analyze_image(content, filename, request.prompt, request.provider)

    return {"answer": answer}


@router.post("/llm", response_model=LlmResponse)
async def api_llm(
    request: LlmRequest
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
async def upsert_chat_message(
    message_data: ChatMessageCreate
):
    """
    Save or update the last summarized message for a conversation.
    """
    async with get_session() as db:
        query = select(ChatMessage).where(
            ChatMessage.tenant_id == message_data.tenant_id,
            ChatMessage.chatwoot_account_id == message_data.chatwoot_account_id,
            ChatMessage.chatwoot_conversation_id == message_data.chatwoot_conversation_id
        )
        result = await db.execute(query)
        chat_message = result.scalar_one_or_none()

        if chat_message:
            chat_message.message_id = message_data.message_id
        else:
            chat_message = ChatMessage(**message_data.model_dump())
            db.add(chat_message)

        await db.commit()
        await db.refresh(chat_message)
        return chat_message

@router.get("/chat_messages", response_model=List[ChatMessageResponse])
async def list_chat_messages(
    tenant_id: int = None,
    chatwoot_account_id: int = None,
    chatwoot_conversation_id: int = None
):
    """
    List tracking records with optional filtering.
    """
    async with get_session() as db:
        query = select(ChatMessage)
        if tenant_id:
            query = query.where(ChatMessage.tenant_id == tenant_id)
        if chatwoot_account_id:
            query = query.where(ChatMessage.chatwoot_account_id == chatwoot_account_id)
        if chatwoot_conversation_id:
            query = query.where(ChatMessage.chatwoot_conversation_id == chatwoot_conversation_id)

        result = await db.execute(query)
        return result.scalars().all()




# --- Global Config CRUD ---

@router.get("/global_configs", response_model=GlobalConfigResponse)
async def get_global_config():
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
    config_data: GlobalConfigCreate
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

# --- Tenant CRUD ---

@router.get("/tenants/{slug}", response_model=TenantFullResponse)
async def get_tenant_by_slug(
    slug: str
):
    """
    Get all tenant details (subscriptions, services, configurations) and global configs by slug.
    """
    async with get_session() as db:
        query = (
            select(Tenant)
            .where(Tenant.slug == slug)
            .options(
                selectinload(Tenant.services),
                selectinload(Tenant.subscriptions),
                selectinload(Tenant.configurations)
            )
        )
        result = await db.execute(query)
        tenant = result.scalar_one_or_none()

        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        global_configs_result = await db.execute(select(GlobalConfig))
        global_configs = global_configs_result.scalars().all()

        services_dict = {svc.name: svc for svc in tenant.services} if tenant.services else {}
        subscription = tenant.subscriptions[0] if tenant.subscriptions else None
        configuration = tenant.configurations[0] if tenant.configurations else None
        global_config = global_configs[0] if global_configs else None

        tenant_response = TenantResponse(
            id=tenant.id,
            slug=tenant.slug,
            created_at=tenant.created_at,
            services=services_dict,
            subscription=subscription,
            configuration=configuration
        )

        return TenantFullResponse(
            tenant=tenant_response,
            global_config=global_config
        )
