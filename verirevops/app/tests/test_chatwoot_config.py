
import asyncio
import sys
import os
from sqlalchemy import select, delete

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.core.db import AsyncSessionLocal
from app.models import Tenant, ChatwootConfig
from app.routers.chatwoot import process_webhook_message # To test logic if possible, or just verify DB

async def main():
    print("--- Starting Chatwoot Config Verification ---")

    async with AsyncSessionLocal() as db:
        # 1. Setup Tenant
        t_id = 881
        alias = "test-chatwoot-tenant"

        # Cleanup
        await db.execute(delete(ChatwootConfig).where(ChatwootConfig.tenant_id == t_id))
        await db.execute(delete(Tenant).where(Tenant.id == t_id))
        await db.commit()

        print("Creating tenant...")
        t = Tenant(id=t_id, name="Chatwoot Test Tenant", slug=alias, url="http://cw-test.com")
        db.add(t)
        await db.commit()

        # 2. CRUD Test - Create Config
        print("Creating Chatwoot Config...")
        config = ChatwootConfig(
            tenant_id=t_id,
            api_url="https://chatwoot.example.com",
            api_access_token="test-token-123",
            account_id=5
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)
        print(f"Config created: ID={config.id}, URL={config.api_url}")

        # 3. Verify Fetch logic (similar to chatwoot.py)
        print("Verifying fetch logic...")
        stmt = select(ChatwootConfig).where(ChatwootConfig.tenant_id == t_id)
        result = await db.execute(stmt)
        fetched_config = result.scalars().first()

        if fetched_config and fetched_config.api_access_token == "test-token-123":
            print("✅ Fetch successful and token matches.")
        else:
            print("❌ Fetch failed or token mismatch.")

        # 4. Cleanup
        print("Cleaning up...")
        await db.execute(delete(ChatwootConfig).where(ChatwootConfig.tenant_id == t_id))
        await db.execute(delete(Tenant).where(Tenant.id == t_id))
        await db.commit()

        print("Verification complete.")

if __name__ == "__main__":
    asyncio.run(main())
