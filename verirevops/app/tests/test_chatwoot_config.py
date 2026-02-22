
import asyncio
import sys
import os
from sqlalchemy import select, delete

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.core.db import AsyncSessionLocal
from app.models import Tenant, IntegrationConfig

async def main():
    print("--- Starting Integration Config Verification ---")

    async with AsyncSessionLocal() as db:
        # 1. Setup Tenant
        t_id = 999
        alias = "test-integration-tenant"

        # Cleanup
        await db.execute(delete(IntegrationConfig).where(IntegrationConfig.tenant_id == t_id))
        await db.execute(delete(Tenant).where(Tenant.id == t_id))
        await db.commit()

        print("Creating tenant...")
        t = Tenant(id=t_id, name="Integration Test Tenant", slug=alias, url="http://int-test.com")
        db.add(t)
        await db.commit()

        # 2. Test Chatwoot Config (Primary Use Case)
        print("Creating Chatwoot Integration Config...")
        cw_config = IntegrationConfig(
            tenant_id=t_id,
            service_name="chatwoot",
            url="https://chatwoot.example.com",
            api_key="test-token-cw",
            account_id="5",
            additional_config={"custom_field": "value"}
        )
        db.add(cw_config)
        await db.commit()

        # verify fetch
        stmt = select(IntegrationConfig).where(
            IntegrationConfig.tenant_id == t_id,
            IntegrationConfig.service_name == "chatwoot"
        )
        result = await db.execute(stmt)
        fetched_cw = result.scalars().first()

        if fetched_cw and fetched_cw.api_key == "test-token-cw":
            print("✅ Chatwoot config stored and retrieved successfully.")
        else:
            print("❌ Chatwoot config verification failed.")

        # 3. Test HubSpot Config (Flexibility Use Case)
        print("Creating HubSpot Integration Config...")
        hs_config = IntegrationConfig(
            tenant_id=t_id,
            service_name="hubspot",
            api_key="pat-na1-xyz", # HubSpot uses access token as API key often
            additional_config={"portal_id": 12345}
        )
        db.add(hs_config)
        await db.commit()

        stmt_hs = select(IntegrationConfig).where(
            IntegrationConfig.tenant_id == t_id,
            IntegrationConfig.service_name == "hubspot"
        )
        result_hs = await db.execute(stmt_hs)
        fetched_hs = result_hs.scalars().first()

        if fetched_hs and fetched_hs.additional_config.get("portal_id") == 12345:
            print("✅ HubSpot config stored and retrieved successfully.")
        else:
            print("❌ HubSpot config verification failed.")

        # 4. Cleanup
        print("Cleaning up...")
        await db.execute(delete(IntegrationConfig).where(IntegrationConfig.tenant_id == t_id))
        await db.execute(delete(Tenant).where(Tenant.id == t_id))
        await db.commit()

        print("Verification complete.")

if __name__ == "__main__":
    asyncio.run(main())
