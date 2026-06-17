from fastapi import APIRouter, Depends, HTTPException

from src.core.auth import require_auth
from src.core.models import User
from src.modules.tenants.schemas import TenantFullResponse
from src.modules.tenants.service import svc_get_tenant_by_slug


router = APIRouter()


@router.get("/tenants/{slug}", response_model=TenantFullResponse)
async def get_tenant_by_slug(slug: str, user: User = Depends(require_auth)):
    """Get full tenant config. Superadmins can access any tenant; tenant users only their own."""
    tenant_data = await svc_get_tenant_by_slug(slug)

    if user.role != "superadmin":
        if user.tenant_id != tenant_data.tenant.id:
            raise HTTPException(status_code=403, detail="Access denied to this tenant")

    return tenant_data
