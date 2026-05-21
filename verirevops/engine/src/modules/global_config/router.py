from fastapi import APIRouter

from src.core.models import GlobalConfigBase
from src.modules.global_config.service import svc_get_global_config, svc_upsert_global_config
from src.modules.global_config.schemas import GlobalConfigResponse


router = APIRouter()


@router.get("/global_configs", response_model=GlobalConfigResponse)
async def get_global_config():
    """
    Get the global configuration.
    """
    return await svc_get_global_config()


@router.post("/global_configs", response_model=GlobalConfigResponse)
async def upsert_global_config(config_data: GlobalConfigBase):
    """
    Upsert the global configuration.
    """
    return await svc_upsert_global_config(config_data)
