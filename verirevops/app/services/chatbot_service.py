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
        """
        Processes an incoming webhook message:
        1. Resolves tenant from alias.
        2. Invokes the chat orchestrator.
        3. Sends the response back to Chatwoot.
        """
        content = data.get("content")
        account_id = data.get("account", {}).get("id")
        conversation = data.get("conversation", {})
        conversation_id = conversation.get("id")
        status = conversation.get("status")

        if not account_id or not conversation_id or not content:
            Log.warning("Incomplete webhook data")
            return

        # 0. Ignore if status is 'open' (Human is handling)
        if status == "open":
            Log.info(f"Conversation {conversation_id} is 'open'. Bot will ignore.")
            return

        try:
            # 1. Resolve Tenant from Alias
            stmt = select(Tenant).where(Tenant.slug == alias)
            result = await self.db.execute(stmt)
            tenant = result.scalars().first()

            if not tenant:
                Log.error(f"Tenant not found for alias: {alias}")
                return

            tenant_id = tenant.id
            Log.tenant(tenant_id, f"Resolved for alias '{alias}'")

            # 2. Invoke Orchestrator
            ai_response, intent = await invoke_chat_orchestrator(tenant_id, conversation_id, content, self.db)
            Log.orchestrator(f"Response: {ai_response} | Intent: {intent}")

            if ai_response:
                # 3. Fetch Chatwoot Config for Tenant
                stmt_config = select(ChatwootConfig).where(ChatwootConfig.tenant_id == tenant_id)
                result_config = await self.db.execute(stmt_config)
                config = result_config.scalars().first()

                client = None
                if config:
                    client = ChatwootClient(base_url=config.api_url, api_token=config.api_access_token)
                else:
                    client = get_chatwoot_client()

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
