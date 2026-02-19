import base64
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Tenant, ChatwootConfig
from app.orchestration.chat import invoke_chat_orchestrator
from app.core.chatwoot import get_chatwoot_client, ChatwootClient
from app.core.logger import Log

class ChatbotService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_webhook_message(self, data: dict, alias: str):
        content = data.get("content") or ""
        account_id = data.get("account", {}).get("id")
        conversation = data.get("conversation", {})
        conversation_id = conversation.get("id")
        status = conversation.get("status")
        raw_attachments = data.get("attachments", [])

        # Guard: Incomplete data
        if not account_id or not conversation_id or (not content and not raw_attachments):
            Log.warning("Incomplete webhook data: No content or attachments")
            return

        # Guard: Human handling
        if status == "open":
            Log.info(f"Conversation {conversation_id} is 'open'. Bot will ignore.")
            return

        try:
            # 1. Resolve Tenant
            tenant = await self._resolve_tenant(alias)
            if not tenant:
                return
            tenant_id = tenant.id

            # 2. Resolve Client
            client = await self._resolve_client(tenant_id)

            # 3. Process Attachments
            attachments = await self._process_attachments(raw_attachments, client)

            # Guard: No content at all
            if raw_attachments and not attachments and not content.strip():
                await self._handle_download_failure(client, account_id, conversation_id)
                return

            # 4. Invoke Orchestrator
            ai_response, intent = await invoke_chat_orchestrator(
                tenant_id, conversation_id, content, self.db, attachments=attachments
            )
            Log.orchestrator(f"Response: {ai_response} | Intent: {intent}")

            # 5. Send Response and Manage Status
            await self._send_ai_response(client, account_id, conversation_id, ai_response, intent)

        except Exception as e:
            Log.error(f"Error in ChatbotService: {e}")
            import traceback
            traceback.print_exc()

    async def _resolve_tenant(self, alias: str):
        """Resolves tenant from alias with guard clause."""
        stmt = select(Tenant).where(Tenant.slug == alias)
        result = await self.db.execute(stmt)
        tenant = result.scalars().first()

        if not tenant:
            Log.error(f"Tenant not found for alias: {alias}")
            return None

        Log.tenant(tenant.id, f"Resolved for alias '{alias}'")
        return tenant

    async def _resolve_client(self, tenant_id: int) -> ChatwootClient:
        """Resolves the appropriate Chatwoot client for the tenant."""
        stmt_config = select(ChatwootConfig).where(ChatwootConfig.tenant_id == tenant_id)
        result_config = await self.db.execute(stmt_config)
        config = result_config.scalars().first()

        if config:
            return ChatwootClient(base_url=config.api_url, api_token=config.api_access_token)

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

    async def _process_attachments(self, raw_attachments: list, client: ChatwootClient) -> list:
        """Processes raw attachments from Chatwoot into a base64-encoded list."""
        if not raw_attachments or not client:
            return []

        attachments = []
        for att in raw_attachments:
            file_url = att.get("data_url")
            file_type = att.get("file_type")

            if not file_url or file_type not in ["image", "audio"]:
                continue

            file_bytes = await client.get_file(file_url)
            if not file_bytes:
                continue

            base64_data = base64.b64encode(file_bytes).decode("utf-8")
            mime_type = att.get("content_type") or ("image/jpeg" if file_type == "image" else "audio/mpeg")

            attachments.append({
                "type": file_type,
                "mime_type": mime_type,
                "data": base64_data
            })

        Log.info(f"Processed {len(attachments)} attachments")
        return attachments
