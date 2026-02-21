import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select
from app.core.db import AsyncSessionLocal
from app.models.chat import ChatSession
from app.models.integration import IntegrationConfig
from app.core.chatwoot import ChatwootClient, get_chatwoot_client
from app.core.logger import Log
from app.models.tenant import Tenant

async def resolve_idle_conversations():
    """
    Identifies conversations that have been idle for more than 60 minutes
    and resolves them in Chatwoot.
    """
    Log.info("🚀 Starting auto-resolution job...")

    idle_threshold = datetime.utcnow() - timedelta(minutes=60)

    async with AsyncSessionLocal() as db:


        # 1. Find sessions that are not resolved and have no activity for > 60m
        # Join with Tenant to ensure we only process ACTIVE tenants
        stmt = (
            select(ChatSession)
            .join(Tenant, ChatSession.tenant_id == Tenant.id)
            .where(
                ChatSession.status != "resolved",
                ChatSession.last_activity_at < idle_threshold,
                Tenant.is_active == True
            )
        )
        result = await db.execute(stmt)
        idle_sessions = result.scalars().all()

        if not idle_sessions:
            Log.info("✅ No idle conversations found.")
            return

        Log.info(f"🔍 Found {len(idle_sessions)} idle conversations. Processing...")

        for session in idle_sessions:
            try:
                # 2. Resolve Chatwoot Client for the tenant
                client = await _resolve_client(db, session.tenant_id)
                if not client:
                    Log.error(f"Could not resolve Chatwoot client for tenant {session.tenant_id}")
                    continue

                # 3. Resolve conversation in Chatwoot
                Log.info(f"🛠 Resolving Conversation {session.chatwoot_conversation_id} (Tenant {session.tenant_id})")
                await client.update_status(
                    session.chatwoot_account_id,
                    session.chatwoot_conversation_id,
                    "resolved"
                )

                # Note: We DON'T update the local status here.
                # We rely on the Chatwoot Webhook to call us back and trigger
                # the summarization flow, which will update the local status.

            except Exception as e:
                Log.error(f"Error resolving session {session.id}: {e}")

async def _resolve_client(db, tenant_id: int) -> ChatwootClient:
    """Resolves the appropriate Chatwoot client for the tenant."""
    stmt_config = select(IntegrationConfig).where(
        IntegrationConfig.tenant_id == tenant_id,
        IntegrationConfig.service_name == "chatwoot"
    )
    result_config = await db.execute(stmt_config)
    config = result_config.scalars().first()

    if config:
        return ChatwootClient(base_url=config.url, api_token=config.api_key)

    return get_chatwoot_client()

if __name__ == "__main__":
    asyncio.run(resolve_idle_conversations())
