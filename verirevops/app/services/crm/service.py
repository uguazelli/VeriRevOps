from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.integration import IntegrationConfig, ContactMapping
from app.services.crm.factory import CRMFactory
from app.schemas.chat import ChatwootContactPayload
from app.core.logger import Log
from app.services.integration_service import IntegrationService
from typing import Dict, Any, Optional

class CRMService:
    """
    Service responsible for synchronizing Chatwoot contacts with external CRMs.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def sync_contact(self, tenant_id: int, payload: ChatwootContactPayload):
        """
        Coordinates the synchronization of a Chatwoot contact to the configured CRM.
        This is designed to be called in a background task.
        """
        # Guard clause: No email, no sync usually
        email = payload.email
        cw_contact_id = payload.id

        if not email or not cw_contact_id:
            Log.warning(f"Skipping CRM sync for tenant {tenant_id}: Missing email or contact ID.")
            return

        # 1. Look for active CRM integrations for this tenant
        integration_service = IntegrationService(self.db)
        configs = await integration_service.get_active_configs(
            tenant_id,
            service_names=["hubspot", "espocrm"]
        )
        if not configs:
            Log.info(f"No active CRM integrations found for tenant {tenant_id}")
            return

        # 2. Sync with each configured CRM
        for config in configs:
            await self._sync_with_adapter(config, payload, cw_contact_id)


    async def _sync_with_adapter(self, config: IntegrationConfig, payload: ChatwootContactPayload, cw_contact_id: int):
        """Internal helper to sync with a specific adapter using persistent mapping."""
        adapter = CRMFactory.get_adapter(config)
        if not adapter:
            Log.error(f"Failed to initialize adapter for {config.service_name}")
            return

        try:
            tenant_id = config.tenant_id
            service_name = config.service_name.lower()
            email = payload.email.lower()
            contact_dict = payload.model_dump()
            contact_dict["email"] = email # Ensure lowercase

            # 1. Check Persistent Mapping first
            external_id = await self._get_mapped_external_id(tenant_id, cw_contact_id, service_name)

            if external_id:
                success = await adapter.update_contact(external_id, contact_dict)
                if success:
                    return
                Log.warning(f"Update failed for {service_name} ID {external_id}. Record might be deleted. Falling back to search.")

            # 2. Fallback: Search by Email
            existing = await adapter.find_contact_by_email(email)

            if existing:
                external_id = existing.get("id")
                Log.info(f"Existing {service_name} contact found via email search: {external_id}. Linking.")
                await adapter.update_contact(external_id, contact_dict)
                await self._save_contact_mapping(tenant_id, cw_contact_id, service_name, external_id)
                return

            # 3. Create new contact
            Log.info(f"Creating new {service_name} contact for {email}")
            new_external_id = await adapter.create_contact(contact_dict)

            if new_external_id:
                await self._save_contact_mapping(tenant_id, cw_contact_id, service_name, new_external_id)

        except Exception as e:
            Log.error(f"Error during {config.service_name} sync: {e}")

    async def _get_mapped_external_id(self, tenant_id: int, cw_contact_id: int, service_name: str) -> Optional[str]:
        """Looks up an external ID in the persistent mapping table."""
        stmt = select(ContactMapping.external_id).where(
            and_(
                ContactMapping.tenant_id == tenant_id,
                ContactMapping.chatwoot_contact_id == cw_contact_id,
                ContactMapping.service_name == service_name
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def _save_contact_mapping(self, tenant_id: int, cw_contact_id: int, service_name: str, external_id: str):
        """Saves or updates a contact mapping in the database."""
        # Use a sub-transactional approach or upsert if available
        # For simplicity in this demo, we'll check and insert
        stmt = select(ContactMapping).where(
            and_(
                ContactMapping.tenant_id == tenant_id,
                ContactMapping.chatwoot_contact_id == cw_contact_id,
                ContactMapping.service_name == service_name
            )
        )
        result = await self.db.execute(stmt)
        mapping = result.scalars().first()

        if mapping:
            mapping.external_id = external_id
        else:
            new_mapping = ContactMapping(
                tenant_id=tenant_id,
                chatwoot_contact_id=cw_contact_id,
                service_name=service_name,
                external_id=external_id
            )
            self.db.add(new_mapping)

        await self.db.commit()
