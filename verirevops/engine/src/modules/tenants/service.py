from fastapi import HTTPException
from sqlalchemy.orm import selectinload
from sqlmodel import select

from src.core.db import get_session
from src.core.models import GlobalConfig, Tenant, TenantFullResponse, TenantResponse


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
