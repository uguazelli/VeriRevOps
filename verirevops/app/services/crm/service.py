from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.integration import IntegrationConfig
from app.services.crm.factory import CRMFactory
from app.core.logger import Log
from typing import Dict, Any, Optional

class CRMService:
    """
    Service responsible for synchronizing Chatwoot contacts with external CRMs.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def sync_contact(self, tenant_id: int, contact_data: Dict[str, Any]):
        """
        Coordinates the synchronization of a Chatwoot contact to the configured CRM.
        This is designed to be called in a background task.
        """
        # Guard clause: No email, no sync usually
        email = contact_data.get("email")
        if not email:
            Log.warning(f"Skipping CRM sync for tenant {tenant_id}: No email provided for contact.")
            return

        # 1. Look for active CRM integrations for this tenant
        configs = await self._get_active_crm_configs(tenant_id)
        if not configs:
            Log.info(f"No active CRM integrations found for tenant {tenant_id}")
            return

        # 2. Sync with each configured CRM
        for config in configs:
            await self._sync_with_adapter(config, contact_data)

    async def _get_active_crm_configs(self, tenant_id: int):
        """Fetches active CRM integration configurations for a tenant."""
        stmt = select(IntegrationConfig).where(
            IntegrationConfig.tenant_id == tenant_id,
            IntegrationConfig.is_active == True,
            IntegrationConfig.service_name.in_(["hubspot", "espocrm"])
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def _sync_with_adapter(self, config: IntegrationConfig, contact_data: Dict[str, Any]):
        """Internal helper to sync with a specific adapter."""
        adapter = CRMFactory.get_adapter(config)
        if not adapter:
            Log.error(f"Failed to initialize adapter for {config.service_name}")
            return

        try:
            email = contact_data.get("email")
            # 1. Try to find existing contact
            existing = await adapter.find_contact_by_email(email)

            if existing:
                external_id = existing.get("id")
                Log.info(f"Updating existing {config.service_name} contact: {external_id}")
                await adapter.update_contact(external_id, contact_data)
                return

            # 2. Create new contact if not found
            Log.info(f"Creating new {config.service_name} contact for {email}")
            await adapter.create_contact(contact_data)

        except Exception as e:
            Log.error(f"Error during {config.service_name} sync: {e}")
