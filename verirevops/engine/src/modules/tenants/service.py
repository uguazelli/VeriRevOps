import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import selectinload
from sqlmodel import select

from src.core.db import get_session
from src.core.models import GlobalConfig, Subscription, Tenant
from src.modules.tenants.schemas import TenantFullResponse, TenantResponse


logger = logging.getLogger(__name__)


async def svc_get_tenant_by_slug(slug: str) -> TenantFullResponse:
    async with get_session() as db:
        query = (
            select(Tenant)
            .where(Tenant.slug == slug)
            .options(
                selectinload(Tenant.services),
                selectinload(Tenant.subscriptions),
                selectinload(Tenant.configurations),
            )
        )
        result = await db.execute(query)
        tenant = result.scalar_one_or_none()

        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")

        global_configs_result = await db.execute(select(GlobalConfig))
        global_configs = global_configs_result.scalars().all()

        services_dict = {svc.name: svc for svc in tenant.services} if tenant.services else {}
        subscription = tenant.subscriptions[0] if tenant.subscriptions else None
        configuration = tenant.configurations[0] if tenant.configurations else None
        global_config = global_configs[0] if global_configs else None

        tenant_response = TenantResponse(
            id=tenant.id,
            slug=tenant.slug,
            created_at=tenant.created_at,
            services=services_dict,
            subscription=subscription,
            configuration=configuration,
        )

        return TenantFullResponse(
            tenant=tenant_response,
            global_config=global_config,
        )


async def svc_has_available_subscription_usage(tenant_id: int) -> bool:
    now = datetime.now(timezone.utc)

    async with get_session() as db:
        query = (
            select(Subscription)
            .where(Subscription.tenant_id == tenant_id)
            .where(Subscription.is_active.is_(True))
            .where(Subscription.start_dat <= now)
            .where(Subscription.end_date >= now)
            .order_by(Subscription.end_date.desc())
        )
        result = await db.execute(query)
        subscription = result.scalars().first()

        if not subscription:
            logger.info(
                "Skipping bot processing for tenant %s because there is no active subscription",
                tenant_id,
            )
            return False

        if subscription.usage_count >= subscription.quota_limit:
            logger.info(
                "Skipping bot processing for tenant %s because subscription %s quota is exhausted (%s/%s)",
                tenant_id,
                subscription.id,
                subscription.usage_count,
                subscription.quota_limit,
            )
            return False

        return True


async def svc_increment_subscription_usage(tenant_id: int) -> bool:
    now = datetime.now(timezone.utc)

    async with get_session() as db:
        query = (
            select(Subscription)
            .where(Subscription.tenant_id == tenant_id)
            .where(Subscription.is_active.is_(True))
            .where(Subscription.start_dat <= now)
            .where(Subscription.end_date >= now)
            .order_by(Subscription.end_date.desc())
            .with_for_update()
        )
        result = await db.execute(query)
        subscription = result.scalars().first()

        if not subscription:
            logger.info(
                "Skipping usage increment for tenant %s because there is no active subscription",
                tenant_id,
            )
            return False

        subscription.usage_count += 1
        await db.commit()

        logger.info(
            "Incremented subscription usage for tenant %s subscription %s (%s/%s)",
            tenant_id,
            subscription.id,
            subscription.usage_count,
            subscription.quota_limit,
        )
        return True
