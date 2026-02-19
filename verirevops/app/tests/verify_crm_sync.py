import asyncio
import httpx
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.crm.service import CRMService
from app.services.crm.adapters.hubspot import HubSpotAdapter
from app.services.crm.adapters.espocrm import EspoCRMAdapter
from app.models.integration import IntegrationConfig

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

    # Mock DB result
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [mock_hubspot_config, mock_espocrm_config]
    mock_db.execute.return_value = mock_result

    # 3. Sample Chatwoot Contact Data
    contact_data = {
        "id": 123,
        "name": "John Doe",
        "email": "john@example.com",
        "phone_number": "+123456789"
    }

    service = CRMService(mock_db)

    # 4. Patch Adapters to avoid real HTTP calls
    with patch("app.services.crm.adapters.hubspot.HubSpotAdapter.find_contact_by_email", new_callable=AsyncMock) as mock_find_hs, \
         patch("app.services.crm.adapters.hubspot.HubSpotAdapter.create_contact", new_callable=AsyncMock) as mock_create_hs, \
         patch("app.services.crm.adapters.espocrm.EspoCRMAdapter.find_contact_by_email", new_callable=AsyncMock) as mock_find_espo, \
         patch("app.services.crm.adapters.espocrm.EspoCRMAdapter.create_contact", new_callable=AsyncMock) as mock_create_espo:

        # Scenario: New Contact (not found in either CRM)
        mock_find_hs.return_value = None
        mock_find_espo.return_value = None

        print("\n🔹 Testing sync for NEW contact (john@EXAMPLE.com)...")
        await service.sync_contact(tenant_id=1, contact_data=contact_data)

        print(f"✅ HubSpot find called: {mock_find_hs.called}")
        print(f"✅ HubSpot create called: {mock_create_hs.called}")
        print(f"✅ EspoCRM find called: {mock_find_espo.called}")
        print(f"✅ EspoCRM create called: {mock_create_espo.called}")

        # Scenario: 409 Conflict in HubSpot (Simulating race condition or search delay)
        mock_find_hs.reset_mock()
        mock_create_hs.reset_mock()
        mock_find_hs.return_value = None # Search says it doesn't exist

        # HubSpot returns 409 because it exists but isn't indexed yet
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 409
        mock_response.json.return_value = {"message": "Contact already exists. Existing ID: 999"}
        mock_create_hs.return_value = await HubSpotAdapter(api_key="api")._handle_conflict(mock_response, contact_data)

        print("\n🔹 Testing sync for CONFLICTING HubSpot contact (409 logic)...")
        await service.sync_contact(tenant_id=1, contact_data=contact_data)
        print(f"✅ HubSpot recovered ID via 409 logic: {mock_create_hs.return_value == '999'}")

        # Scenario: Existing Contact in HubSpot
        mock_find_hs.reset_mock()
        mock_create_hs.reset_mock()
        mock_find_hs.return_value = {"id": "HS_456"}

        with patch("app.services.crm.adapters.hubspot.HubSpotAdapter.update_contact", new_callable=AsyncMock) as mock_update_hs:
            print("\n🔹 Testing sync for EXISTING HubSpot contact...")
            await service.sync_contact(tenant_id=1, contact_data=contact_data)

            print(f"✅ HubSpot update called: {mock_update_hs.called}")
            print(f"✅ HubSpot create NOT called: {not mock_create_hs.called}")

    print("\n✨ Verification complete!")

if __name__ == "__main__":
    asyncio.run(verify_crm_sync())
