import base64
from typing import Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models import Tenant, IntegrationConfig, Subscription, ChatSession
from app.orchestration.chat import invoke_chat_orchestrator
from app.core.chatwoot import get_chatwoot_client, ChatwootClient
from app.schemas.chat import ChatwootMessagePayload, ChatwootAttachment
from app.core.logger import Log

class ChatbotService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_webhook_message(self, payload: ChatwootMessagePayload, alias: str):
        content = payload.content or ""
        account_id = payload.account.id if payload.account else None
        conversation_id = payload.conversation.id if payload.conversation else None
        status = payload.conversation.status if payload.conversation else None

        if not account_id or not conversation_id:
            Log.warning(f"Incomplete message payload: account_id={account_id}, conversation_id={conversation_id}")
            return

        # 1. Resolve Tenant
        tenant = await self._resolve_tenant(alias)
        if not tenant:
            return
        tenant_id = tenant.id

        # Update Session Activity and Status
        await self._update_session_activity(tenant_id, account_id, conversation_id, status)

        # Guard: Human handling
        if status == "open":
            Log.info(f"Conversation {conversation_id} is 'open'. Bot will ignore.")
            return

        # 2. Resolve Subscription
        subscription = await self._resolve_subscription(tenant_id, alias)
        if not subscription:
            return

        # 3. Resolve Client
        client = await self._resolve_client(tenant_id)

        # 3. Process Attachments
        attachments = await self._process_attachments(payload.attachments, client)

        # Guard: No content at all
        if payload.attachments and not attachments and not content.strip():
            await self._handle_download_failure(client, account_id, conversation_id)
            return

        # 4. Invoke Orchestrator
        ai_response, intent = await invoke_chat_orchestrator(
            tenant_id, account_id, conversation_id, content, self.db, client, attachments=attachments
        )
        Log.orchestrator(f"Response: {ai_response} | Intent: {intent}")

        # 6. Send Response and Manage Status
        await self._send_ai_response(client, account_id, conversation_id, ai_response, intent)

        # 7. Increment Usage
        stmt_inc = (
            update(Subscription)
            .where(Subscription.id == subscription.id)
            .values(usage_count=Subscription.usage_count + 1)
        )
        await self.db.execute(stmt_inc)
        await self.db.commit()
        Log.info(f"Incremented usage for tenant {tenant_id}. New count: {subscription.usage_count + 1}")

    async def _resolve_tenant(self, alias: str):
        """Resolves tenant from alias with guard clause and activation check."""
        stmt = select(Tenant).where(Tenant.slug == alias)
        result = await self.db.execute(stmt)
        tenant = result.scalars().first()

        if not tenant:
            Log.error(f"Tenant not found for alias: {alias}")
            return None

        if not tenant.is_active:
            Log.warning(f"Tenant {tenant.id} ({alias}) is inactive. Operation aborted.")
            return None

        Log.tenant(tenant.id, f"Resolved for alias '{alias}'")
        return tenant

    async def _resolve_subscription(self, tenant_id: int, alias: str) -> Optional[Subscription]:
        """Resolves and validates subscription for a tenant."""
        stmt_sub = select(Subscription).where(Subscription.tenant_id == tenant_id)
        result_sub = await self.db.execute(stmt_sub)
        subscription = result_sub.scalars().first()

        if not subscription:
            Log.warning(f"Tenant {tenant_id} '{alias}' has no active subscription.")
            return None

        # Check limits
        now = datetime.now()
        if subscription.end_date and now > subscription.end_date:
            Log.warning(f"Tenant {tenant_id} subscription expired on {subscription.end_date}.")
            return None

        if subscription.usage_count >= subscription.quota_limit:
            Log.warning(f"Tenant {tenant_id} quota reached: {subscription.usage_count}/{subscription.quota_limit}")
            return None

        return subscription

    async def _resolve_client(self, tenant_id: int) -> ChatwootClient:
        """Resolves the appropriate Chatwoot client for the tenant."""
        stmt_config = select(IntegrationConfig).where(
            IntegrationConfig.tenant_id == tenant_id,
            IntegrationConfig.service_name == "chatwoot"
        )
        result_config = await self.db.execute(stmt_config)
        config = result_config.scalars().first()

        if config:
            return ChatwootClient(base_url=config.url, api_token=config.api_key)

        return get_chatwoot_client()

    async def _handle_download_failure(self, client: ChatwootClient, account_id: int, conversation_id: int):
        """Handles notification when attachments fail to download."""
        Log.warning("Failed to download any attachments and no text content provided.")
        if client:
            await client.send_message(
                account_id,
                conversation_id,
                "⚠️ Sorry, I couldn't access the file you sent. Please try sending it again or describe what you need."
            )

    async def _send_ai_response(self, client: ChatwootClient, account_id: int, conversation_id: int, ai_response: str, intent: str):
        """Sends the AI response and updates conversation status."""
        if not ai_response:
            return

        if not client:
            Log.warning(f"Chatwoot client missing while trying to send response.")
            return

        # Send actual message
        await client.send_message(account_id, conversation_id, ai_response)
        Log.webhook(f"Sent response to Chatwoot", direction="OUT")

        # Update Status
        new_status = "open" if intent == "handoff" else "pending"
        await client.update_status(account_id, conversation_id, new_status)

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

    async def _update_session_activity(self, tenant_id: int, account_id: int, conversation_id: int, status: str):
        """Updates the last_activity_at and status for a chat session."""
        stmt = (
            update(ChatSession)
            .where(
                ChatSession.tenant_id == tenant_id,
                ChatSession.chatwoot_account_id == account_id,
                ChatSession.chatwoot_conversation_id == conversation_id
            )
            .values(
                last_activity_at=datetime.utcnow(),
                status=status
            )
        )
        result = await self.db.execute(stmt)
        if result.rowcount == 0:
            new_session = ChatSession(
                id=conversation_id,
                tenant_id=tenant_id,
                chatwoot_account_id=account_id,
                chatwoot_conversation_id=conversation_id,
                status=status,
                last_activity_at=datetime.utcnow()
            )
            self.db.add(new_session)

        await self.db.commit()
        Log.info(f"Updated activity for session {conversation_id} (Status: {status})")
