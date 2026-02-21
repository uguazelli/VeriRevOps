from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.models.tenant import Tenant
from app.core.logger import Log

class TenantService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_tenant(self, alias: str) -> Optional[Tenant]:
        """Resolves tenant from alias with guard clause and activation check."""
        stmt = select(Tenant).where(Tenant.slug == alias)
        result = await self.db.execute(stmt)
        tenant = result.scalars().first()

        if not tenant:
            Log.error(f"Tenant not found for alias: {alias}")
            return None

        if not tenant.is_active:
            Log.warning(f"Tenant {tenant.id} ({alias}) is inactive. Operation aborted.")
            return None

        Log.tenant(tenant.id, f"Resolved for alias '{alias}'")
        return tenant

    async def get_or_create_tenant(self, tenant_id: int) -> Optional[Tenant]:
        """
        Ensures a tenant exists in the database.
        Used for auto-provisioning during orchestration if the tenant is missing.
        """
        stmt = select(Tenant).where(Tenant.id == tenant_id)
        result = await self.db.execute(stmt)
        tenant = result.scalars().first()

        if tenant:
            return tenant

        # Auto-provisioning logic
        try:
            Log.info(f"Auto-provisioning missing tenant {tenant_id}")
            tenant = Tenant(
                id=tenant_id,
                name=f"Tenant {tenant_id}",
                slug=f"tenant-{tenant_id}",
                url=f"https://example.com/tenant-{tenant_id}"
            )
            self.db.add(tenant)
            await self.db.flush()
            return tenant
        except IntegrityError:
            await self.db.rollback()
            result = await self.db.execute(stmt)
            return result.scalars().first()
