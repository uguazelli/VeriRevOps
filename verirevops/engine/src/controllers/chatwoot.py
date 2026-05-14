import json
from fastapi import APIRouter
from src.services.chatwoot import (
    process_chatwoot_payload,
    get_message_kind,
    transcribe_audio as transcribe_chatwoot_audio,
    analyze_image as analyze_chatwoot_image,
)
from src.services.tenants import svc_get_tenant_by_slug


router = APIRouter()

@router.post("/chatwoot/webhook/{slug}")
async def chatwoot_webhook(
    slug: str,
    payload: dict
):
    """
    Endpoint to receive webhooks from Chatwoot.
    """

    # print(
    #     f"🛜 Received Chatwoot webhook for tenant '{slug}': "
    #     f"{json.dumps(payload, indent=2)}"
    # )

    # 1 - Check if bot should respond to this message
    should_respond = process_chatwoot_payload(payload)
    print(f"✅ Processed payload result: {should_respond}")

    message_kind = get_message_kind(payload)
    print(f"🏞️ Message kind: {message_kind}")

    # 2 - Get tenant settings
    tenant_settings = await svc_get_tenant_by_slug(slug)
    # print(f"Tenant settings for '{slug}':")
    # print(tenant_settings.model_dump_json(indent=2))

    # 3 - If audio message, transcribe it
    transcription = None
    if message_kind == "audio":
        print("🎤 Transcribing audio message...")
        transcription = await transcribe_chatwoot_audio(payload)
        print(f"Transcription result: {transcription}")

    # 4 - If image message, describe it
    image_description = None
    if message_kind == "image":
        print("🖼️ Describing image message...")
        image_description = await analyze_chatwoot_image(payload)
        print(f"Image description: {image_description}")

    # 5 - Get message history from Chatwoot API
    # 5 - Classify if it requires RAG, handle to a human or if is just a small talk
    # 6 - If small talk, generate answer with LLM and send to Chatwoot API
    # 7 - If Handle to human, send message to Chatwoot API and update status to open
    # 8 - If RAG, generate answer with retrieved context and send to Chatwoot API



    return {
        "status": "success",
        "message_kind": message_kind,
        "transcription": transcription,
        "image_description": image_description
    }
