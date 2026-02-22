from datetime import datetime
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.tenant import Subscription
from app.core.logger import Log

class SubscriptionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_subscription(self, tenant_id: int, alias: str = "") -> Optional[Subscription]:
        """Resolves and validates subscription for a tenant."""
        stmt = select(Subscription).where(Subscription.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        subscription = result.scalars().first()

        if not subscription:
            Log.warning(f"Tenant {tenant_id} '{alias}' has no active subscription.")
            return None

        # Check limits
        now = datetime.now()
        if subscription.end_date and now > subscription.end_date:
            Log.warning(f"Tenant {tenant_id} subscription expired on {subscription.end_date}.")
            return None

        if subscription.usage_count >= subscription.quota_limit:
            Log.warning(f"Tenant {tenant_id} quota reached: {subscription.usage_count}/{subscription.quota_limit}")
            return None

        return subscription

    async def increment_usage(self, subscription_id: int):
        """Increments the usage count for a subscription."""
        stmt = (
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(usage_count=Subscription.usage_count + 1)
        )
        await self.db.execute(stmt)
        await self.db.commit()
        Log.info(f"Incremented usage for subscription {subscription_id}.")
