from fastapi import APIRouter, Depends

from src.core.auth import require_superadmin
from src.core.models import GlobalConfigBase, User
from src.modules.global_config.schemas import GlobalConfigResponse
from src.modules.global_config.service import svc_get_global_config, svc_upsert_global_config


router = APIRouter()


@router.get("/global_configs", response_model=GlobalConfigResponse)
async def get_global_config(user: User = Depends(require_superadmin)):
    return await svc_get_global_config()


@router.post("/global_configs", response_model=GlobalConfigResponse)
async def upsert_global_config(
    config_data: GlobalConfigBase,
    user: User = Depends(require_superadmin),
):
    return await svc_upsert_global_config(config_data)
