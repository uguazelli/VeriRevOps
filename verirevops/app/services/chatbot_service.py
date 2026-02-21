import base64
from typing import Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models import Tenant, IntegrationConfig, Subscription, ChatSession
from app.orchestration.chat import invoke_chat_orchestrator
from app.core.chatwoot import get_chatwoot_client, ChatwootClient
from app.schemas.chat import ChatwootMessagePayload, ChatwootAttachment, SessionKey, OrchestrationInput
from app.core.logger import Log
from app.services.tenant_service import TenantService
from app.services.integration_service import IntegrationService
from app.services.chat_session_service import ChatSessionService
from app.services.subscription_service import SubscriptionService

class ChatbotService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_webhook_message(self, payload: ChatwootMessagePayload, alias: str):
        if not payload.account or not payload.conversation:
            Log.warning(f"Incomplete message payload: missing account or conversation objects")
            return

        # 1. Resolve Tenant
        tenant_service = TenantService(self.db)
        tenant = await tenant_service.resolve_tenant(alias)
        if not tenant:
            return

        # 1.1 Construct Session Key
        session_key = SessionKey(
            tenant_id=tenant.id,
            account_id=payload.account.id,
            conversation_id=payload.conversation.id
        )

        # Update Session Activity and Status
        chat_session_service = ChatSessionService(self.db)
        await chat_session_service.update_session_activity(session_key, payload.conversation.status)

        # Guard: Human handling
        if payload.conversation.status == "open":
            Log.info(f"Conversation {session_key.conversation_id} is 'open'. Bot will ignore.")
            return

        # 2. Resolve Subscription
        subscription_service = SubscriptionService(self.db)
        subscription = await subscription_service.validate_subscription(session_key.tenant_id, alias)
        if not subscription:
            return

        # 3. Resolve Client
        integration_service = IntegrationService(self.db)
        client = await integration_service.resolve_chatwoot_client(session_key.tenant_id)

        # 3. Process Attachments
        attachments = await self._process_attachments(payload.attachments, client)

        # Guard: No content at all
        content = payload.content or ""
        if payload.attachments and not attachments and not content.strip():
            await self._handle_download_failure(client, session_key.account_id, session_key.conversation_id)
            return

        # 4. Invoke Orchestrator
        orch_input = OrchestrationInput(
            session_key=session_key,
            user_message=content,
            attachments=attachments
        )
        ai_response, intent = await invoke_chat_orchestrator(
            input_data=orch_input,
            db=self.db,
            chatwoot_client=client
        )
        Log.orchestrator(f"Response: {ai_response} | Intent: {intent}")

        # 6. Send Response and Manage Status
        await self._send_ai_response(client, session_key, ai_response, intent)

        # 7. Increment Usage
        await subscription_service.increment_usage(subscription.id)




    async def _handle_download_failure(self, client: ChatwootClient, account_id: int, conversation_id: int):
        """Handles notification when attachments fail to download."""
        Log.warning("Failed to download any attachments and no text content provided.")
        if client:
            await client.send_message(
                account_id,
                conversation_id,
                "⚠️ Sorry, I couldn't access the file you sent. Please try sending it again or describe what you need."
            )

    async def _send_ai_response(self, client: ChatwootClient, key: SessionKey, ai_response: str, intent: str):
        """Sends the AI response and updates conversation status."""
        if not ai_response:
            return

        if not client:
            Log.warning(f"Chatwoot client missing while trying to send response.")
            return

        # Send actual message
        await client.send_message(key.account_id, key.conversation_id, ai_response)
        Log.webhook(f"Sent response to Chatwoot", direction="OUT")

        # Update Status
        new_status = "open" if intent == "handoff" else "pending"
        await client.update_status(key.account_id, key.conversation_id, new_status)

    async def _process_attachments(self, raw_attachments: list[ChatwootAttachment], client: ChatwootClient) -> list:
        """Processes raw attachments from Chatwoot into a base64-encoded list."""
        if not raw_attachments or not client:
            return []

        attachments = []
        for att in raw_attachments:
            file_url = att.data_url
            file_type = att.file_type

            if not file_url or file_type not in ["image", "audio"]:
                continue

            file_bytes = await client.get_file(file_url)
            if not file_bytes:
                continue

            base64_data = base64.b64encode(file_bytes).decode("utf-8")
            mime_type = att.content_type or ("image/jpeg" if file_type == "image" else "audio/mpeg")

            attachments.append({
                "type": file_type,
                "mime_type": mime_type,
                "data": base64_data
            })

        Log.info(f"Processed {len(attachments)} attachments")
        return attachments

