from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
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
