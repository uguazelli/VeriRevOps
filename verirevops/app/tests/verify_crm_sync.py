import asyncio
import httpx
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.crm.service import CRMService
from app.services.crm.adapters.hubspot import HubSpotAdapter
from app.services.crm.adapters.espocrm import EspoCRMAdapter
from app.models.integration import IntegrationConfig, ContactMapping

async def verify_crm_sync():
    print("🚀 Starting CRM Sync Verification...")

    # 1. Mock Database Session
    mock_db = AsyncMock()

    # 2. Mock Integration Configs
    mock_hubspot_config = IntegrationConfig(
        tenant_id=1,
        service_name="hubspot",
        api_key="fake_hubspot_key",
        is_active=True
    )
    mock_espocrm_config = IntegrationConfig(
        tenant_id=1,
        service_name="espocrm",
        url="https://crm.work.com",
        api_key="fake_espo_key",
        is_active=True
    )

    # Mock DB configurations result
    mock_config_result = MagicMock()
    mock_config_result.scalars().all.return_value = [mock_hubspot_config, mock_espocrm_config]

    # Simple mock for execute to handle multiple different queries
    async def mock_execute(stmt):
        stmt_str = str(stmt)
        # If it's looking for IntegrationConfig
        if "integration_configs" in stmt_str:
            return mock_config_result
        # If it's looking for ContactMapping
        if "contact_mappings" in stmt_str:
            m = MagicMock()
            current_mapping = getattr(mock_db, "_current_mapping", None)

            # If the query is specifically for external_id column
            if "external_id" in stmt_str and "FROM contact_mappings" in stmt_str:
                ext_id = current_mapping.external_id if current_mapping else None
                m.scalars().first.return_value = ext_id
            else:
                m.scalars().first.return_value = current_mapping
            return m
        return MagicMock()

    mock_db.execute.side_effect = mock_execute
    mock_db.add = AsyncMock() # Mock db.add for new mapping creation
    mock_db.commit = AsyncMock() # Mock db.commit

    # 3. Sample Chatwoot Contact Data
    contact_data = {
        "id": 123,
        "name": "John Doe",
        "email": "john@example.com",
        "phone_number": "+123456789"
    }

    service = CRMService(mock_db)

    # 4. Patch Adapters
    with patch("app.services.crm.adapters.hubspot.HubSpotAdapter.find_contact_by_email", new_callable=AsyncMock) as mock_find_hs, \
         patch("app.services.crm.adapters.hubspot.HubSpotAdapter.create_contact", new_callable=AsyncMock) as mock_create_hs, \
         patch("app.services.crm.adapters.hubspot.HubSpotAdapter.update_contact", new_callable=AsyncMock) as mock_update_hs, \
         patch("app.services.crm.adapters.espocrm.EspoCRMAdapter.find_contact_by_email", new_callable=AsyncMock) as mock_find_espo, \
         patch("app.services.crm.adapters.espocrm.EspoCRMAdapter.create_contact", new_callable=AsyncMock) as mock_create_espo:

        # Scenario 1: Persistent Mapping Found (Direct Update)
        mock_db._current_mapping = ContactMapping(
            tenant_id=1,
            chatwoot_contact_id=123,
            service_name="hubspot",
            external_id="HS_MAPPED_789"
        )
        mock_update_hs.return_value = True

        print("\n🔹 Testing sync with PERSISTENT MAPPING (Direct Update)...")
        await service.sync_contact(tenant_id=1, contact_data=contact_data)

        print(f"✅ HubSpot update called directly: {mock_update_hs.called}")
        print(f"✅ HubSpot search NOT called: {not mock_find_hs.called}")
        mock_update_hs.reset_mock()
        mock_find_hs.reset_mock()
        mock_db.add.reset_mock()

        # Scenario 2: No Mapping, Found by Email (Fallback + Creating Mapping)
        mock_db._current_mapping = None
        mock_find_hs.return_value = {"id": "HS_SEARCH_101"}
        mock_update_hs.return_value = True # Assume update is successful

        print("\n🔹 Testing sync with FALLBACK SEARCH (Mapping Creation)...")
        await service.sync_contact(tenant_id=1, contact_data=contact_data)

        print(f"✅ HubSpot search called: {mock_find_hs.called}")
        print(f"✅ HubSpot update called: {mock_update_hs.called}")
        # Verify db.add was called for the new mapping
        print(f"✅ New mapping created (db.add check): {mock_db.add.called}")
        mock_update_hs.reset_mock()
        mock_find_hs.reset_mock()
        mock_db.add.reset_mock()

        # Scenario 3: 409 Conflict in HubSpot (Recovery + Mapping Creation)
        mock_find_hs.return_value = None

        # Simulating the static method fix/behavior
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 409
        mock_response.json.return_value = {"message": "Contact already exists. Existing ID: 999"}

        with patch("app.services.crm.adapters.hubspot.HubSpotAdapter.create_contact", new_callable=AsyncMock) as mock_create_hs_conflict:
            # We mock the internal _handle_conflict result
            mock_create_hs_conflict.side_effect = httpx.HTTPStatusError(
                "Conflict", request=MagicMock(), response=mock_response
            )
            # Also mock the _handle_conflict method directly if it's called
            with patch("app.services.crm.adapters.hubspot.HubSpotAdapter._handle_conflict", new_callable=AsyncMock) as mock_handle_conflict:
                mock_handle_conflict.return_value = "999"

                print("\n🔹 Testing sync with 409 CONFLICT RECOVERY...")
                await service.sync_contact(tenant_id=1, contact_data=contact_data)
                print(f"✅ New mapping created after conflict recovery: {mock_db.add.called}")
        mock_db.add.reset_mock()

        # Scenario 4: New Contact (not found in either CRM) - Original test re-integrated
        mock_find_hs.reset_mock()
        mock_create_hs.reset_mock()
        mock_find_espo.reset_mock()
        mock_create_espo.reset_mock()
        mock_db._current_mapping = None
        mock_find_hs.return_value = None
        mock_find_espo.return_value = None
        mock_create_hs.return_value = "HS_NEW_123"
        mock_create_espo.return_value = "ESPO_NEW_456"

        print("\n🔹 Testing sync for NEW contact (john@EXAMPLE.com)...")
        await service.sync_contact(tenant_id=1, contact_data=contact_data)

        print(f"✅ HubSpot find called: {mock_find_hs.called}")
        print(f"✅ HubSpot create called: {mock_create_hs.called}")
        print(f"✅ EspoCRM find called: {mock_find_espo.called}")
        print(f"✅ EspoCRM create called: {mock_create_espo.called}")
        print(f"✅ New mapping created for HubSpot: {mock_db.add.call_count >= 1}")
        print(f"✅ New mapping created for EspoCRM: {mock_db.add.call_count >= 2}")
        mock_db.add.reset_mock()


    print("\n✨ Verification complete!")

if __name__ == "__main__":
    asyncio.run(verify_crm_sync())
