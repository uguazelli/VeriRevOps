from typing import List
from fastapi import APIRouter, UploadFile, File, Form
from src.core.models import (
    ContactMappingCreate, ContactMappingUpdate, ContactMappingResponse,
    ChatMessageCreate, ChatMessageResponse,
    GlobalConfigCreate, GlobalConfigResponse, TenantFullResponse
)
from src.core.schemas import (
    RagRequest, RagResponse, LlmRequest, LlmResponse,
    TranscribeUrlRequest, AnalyzeImageUrlRequest
)
from src.services.rag import generate_answer
from src.services.transcription import transcribe_audio
from src.services.llm import get_chat_response
from src.services.image_analysis import analyze_image
from src.services.media_downloader import download_file_from_url
from src.services.contact_mappings import (
    svc_list_contact_mappings, svc_create_contact_mapping,
    svc_update_contact_mapping, svc_delete_contact_mapping
)
from src.services.chat_messages import svc_upsert_chat_message, svc_list_chat_messages
from src.services.global_configs import svc_get_global_config, svc_upsert_global_config
from src.services.tenants import svc_get_tenant_by_slug

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

# --- Contact Mappings CRUD ---

@router.get("/contact_mappings", response_model=List[ContactMappingResponse])
async def list_contact_mappings(
    tenant_id: int = None,
    chatwoot_contact_id: int = None,
    service_name: str = None
):
    """
    List contact mappings with optional filtering.
    """
    return await svc_list_contact_mappings(tenant_id, chatwoot_contact_id, service_name)

@router.post("/contact_mappings", response_model=ContactMappingResponse)
async def create_contact_mapping(
    mapping_data: ContactMappingCreate
):
    """
    Create a new contact mapping. Returns 409 if it already exists.
    """
    return await svc_create_contact_mapping(mapping_data)

@router.put("/contact_mappings/{chatwoot_contact_id}", response_model=ContactMappingResponse)
async def update_contact_mapping(
    chatwoot_contact_id: int,
    mapping_data: ContactMappingUpdate
):
    """
    Update an existing contact mapping by chatwoot_contact_id, tenant_id, and service_name.
    """
    return await svc_update_contact_mapping(chatwoot_contact_id, mapping_data)

@router.delete("/contact_mappings/{mapping_id}")
async def delete_contact_mapping(
    mapping_id: int
):
    """
    Delete a contact mapping by its database ID.
    """
    count = await svc_delete_contact_mapping(mapping_id)
    return {"deleted_count": count}

# --- Chat Messages CRUD ---

@router.post("/chat_messages", response_model=ChatMessageResponse)
async def upsert_chat_message(
    message_data: ChatMessageCreate
):
    """
    Save or update the last summarized message for a conversation.
    """
    return await svc_upsert_chat_message(message_data)

@router.get("/chat_messages", response_model=List[ChatMessageResponse])
async def list_chat_messages(
    tenant_id: int = None,
    chatwoot_account_id: int = None,
    chatwoot_conversation_id: int = None
):
    """
    List tracking records with optional filtering.
    """
    return await svc_list_chat_messages(tenant_id, chatwoot_account_id, chatwoot_conversation_id)

# --- Global Config CRUD ---

@router.get("/global_configs", response_model=GlobalConfigResponse)
async def get_global_config():
    """
    Get the global configuration (assumes single row with id=1).
    """
    return await svc_get_global_config()

@router.post("/global_configs", response_model=GlobalConfigResponse)
async def upsert_global_config(
    config_data: GlobalConfigCreate
):
    """
    Upsert the single global configuration (id=1).
    """
    return await svc_upsert_global_config(config_data)

# --- Tenant CRUD ---

@router.get("/tenants/{slug}", response_model=TenantFullResponse)
async def get_tenant_by_slug(
    slug: str
):
    """
    Get all tenant details (subscriptions, services, configurations) and global configs by slug.
    """
    return await svc_get_tenant_by_slug(slug)
