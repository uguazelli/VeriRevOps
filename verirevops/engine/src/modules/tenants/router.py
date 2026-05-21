from fastapi import APIRouter

from src.modules.tenants.service import svc_get_tenant_by_slug
from src.modules.tenants.schemas import TenantFullResponse


router = APIRouter()


@router.get("/tenants/{slug}", response_model=TenantFullResponse)
async def get_tenant_by_slug(slug: str):
    """
    Get all tenant details, service settings, subscription, configuration, and global config by slug.
    """
    return await svc_get_tenant_by_slug(slug)
