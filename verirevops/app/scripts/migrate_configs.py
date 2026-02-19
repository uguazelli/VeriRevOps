
import asyncio
import sys
import os
from sqlalchemy import select, text

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.core.db import AsyncSessionLocal, engine
from app.core.db import AsyncSessionLocal, engine
from app.models import IntegrationConfig, Base
from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

class ChatwootConfig(Base):
    __tablename__ = "chatwoot_configs"
    __table_args__ = {'extend_existing': True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False) # No ForeignKey needed for migration reading
    api_url: Mapped[str] = mapped_column(String, nullable=False)
    api_access_token: Mapped[str] = mapped_column(String, nullable=False)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

async def migrate():
    print("--- Starting Configuration Migration ---")

    async with AsyncSessionLocal() as db:
        # 0. Create generic table if not exists (using SQLAlchemy to create)
        # In a real production setup with Alembic, this step wouldn't be here like this.
        # But since we lack Alembic, we must ensure the table exists.
        print("Ensuring tables exist...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # 1. Fetch old configs
        print("Fetching legacy Chatwoot configurations...")
        stmt = select(ChatwootConfig)
        result = await db.execute(stmt)
        old_configs = result.scalars().all()

        print(f"Found {len(old_configs)} configurations to migrate.")

        migrated_count = 0
        for old in old_configs:
            # Check if already exists
            stmt_check = select(IntegrationConfig).where(
                IntegrationConfig.tenant_id == old.tenant_id,
                IntegrationConfig.service_name == "chatwoot"
            )
            existing = await db.execute(stmt_check)
            if existing.scalars().first():
                print(f"Skipping Tenant {old.tenant_id}: Already migrated.")
                continue

            # Create new config
            new_config = IntegrationConfig(
                tenant_id=old.tenant_id,
                service_name="chatwoot",
                url=old.api_url,
                api_key=old.api_access_token,
                account_id=str(old.account_id),
                additional_config={}, # Empty for now as all fields mapped
                is_active=True
            )
            db.add(new_config)
            migrated_count += 1

        await db.commit()
        print(f"Successfully migrated {migrated_count} configurations.")
        print("--- Migration Complete ---")

if __name__ == "__main__":
    try:
        asyncio.run(migrate())
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
