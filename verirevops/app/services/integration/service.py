from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.integration import IntegrationConfig
from app.core.chatwoot import get_chatwoot_client, ChatwootClient
from app.core.logger import Log

class IntegrationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_configs(self, tenant_id: int, service_names: Optional[List[str]] = None) -> List[IntegrationConfig]:
        """Fetches active integration configurations for a tenant."""
        stmt = select(IntegrationConfig).where(
            IntegrationConfig.tenant_id == tenant_id,
            IntegrationConfig.is_active == True
        )
        if service_names:
            stmt = stmt.where(IntegrationConfig.service_name.in_(service_names))

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def resolve_chatwoot_client(self, tenant_id: int) -> Optional[ChatwootClient]:
        """Resolves the appropriate Chatwoot client for the tenant."""
        stmt = select(IntegrationConfig).where(
            IntegrationConfig.tenant_id == tenant_id,
            IntegrationConfig.service_name == "chatwoot"
        )
        result = await self.db.execute(stmt)
        config = result.scalars().first()

        if config:
            return ChatwootClient(base_url=config.url, api_token=config.api_key)

        client = get_chatwoot_client()
        if not client:
             Log.warning(f"Chatwoot configuration missing for tenant {tenant_id} and no global default found.")
        return client
