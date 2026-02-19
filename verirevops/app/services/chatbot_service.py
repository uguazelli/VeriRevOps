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

        # Ignore if no account_id or conversation_id or no content and no attachments
        if not account_id or not conversation_id or (not content and not raw_attachments):
            Log.warning("Incomplete webhook data: No content or attachments")
            return

        # Ignore if status is 'open' (Human is handling)
        if status == "open":
            Log.info(f"Conversation {conversation_id} is 'open'. Bot will ignore.")
            return


        try:
            # Resolve Tenant from Alias
            stmt = select(Tenant).where(Tenant.slug == alias)
            result = await self.db.execute(stmt)
            tenant = result.scalars().first()

            # Ignore if tenant not found
            if not tenant:
                Log.error(f"Tenant not found for alias: {alias}")
                return

            tenant_id = tenant.id
            Log.tenant(tenant_id, f"Resolved for alias '{alias}'")

            # Fetch Chatwoot Config and Client
            stmt_config = select(ChatwootConfig).where(ChatwootConfig.tenant_id == tenant_id)
            result_config = await self.db.execute(stmt_config)
            config = result_config.scalars().first()

            client = None
            if config:
                client = ChatwootClient(base_url=config.api_url, api_token=config.api_access_token)
            else:
                client = get_chatwoot_client()

            # Process Attachments
            attachments = []
            if raw_attachments and client:
                for att in raw_attachments:
                    file_url = att.get("data_url")
                    file_type = att.get("file_type")
                    if file_url and file_type in ["image", "audio"]:
                        file_bytes = await client.get_file(file_url)
                        if file_bytes:
                            base64_data = base64.b64encode(file_bytes).decode('utf-8')
                            attachments.append({
                                "type": file_type,
                                "mime_type": att.get("content_type", "image/jpeg" if file_type == "image" else "audio/mpeg"),
                                "data": base64_data
                            })
                Log.info(f"Processed {len(attachments)} attachments")

            # Fallback if no text AND all downloads failed
            if raw_attachments and not attachments and not content.strip():
                Log.warning("Failed to download any attachments and no text content provided.")
                if client:
                    await client.send_message(
                        account_id,
                        conversation_id,
                        "Desculpe, não consegui acessar o arquivo que você enviou agora. Pode ser um erro temporário do servidor. Você poderia tentar enviar novamente ou descrever o que precisa?"
                    )
                return

            # Invoke Orchestrator
            ai_response, intent = await invoke_chat_orchestrator(tenant_id, conversation_id, content, self.db, attachments=attachments)
            Log.orchestrator(f"Response: {ai_response} | Intent: {intent}")

            if ai_response:
                if client:
                    await client.send_message(account_id, conversation_id, ai_response)
                    Log.webhook(f"Sent response to Chatwoot", direction="OUT")

                    # 4. Status Management
                    new_status = "open" if intent == "handoff" else "pending"
                    await client.update_status(account_id, conversation_id, new_status)
                else:
                    Log.warning(f"Chatwoot client not configured for Tenant {tenant_id}")
        except Exception as e:
            Log.error(f"Error in ChatbotService: {e}")
            import traceback
            traceback.print_exc()
