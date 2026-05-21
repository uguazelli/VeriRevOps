from fastapi import HTTPException
from sqlmodel import select

from src.core.db import get_session
from src.core.models import GlobalConfig, GlobalConfigBase


async def svc_get_global_config() -> GlobalConfig:
    async with get_session() as db:
        result = await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))
        config = result.scalar_one_or_none()

        if not config:
            raise HTTPException(status_code=404, detail="Global config not found")

        return config


async def svc_upsert_global_config(config_data: GlobalConfigBase) -> GlobalConfig:
    async with get_session() as db:
        result = await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))
        config = result.scalar_one_or_none()

        if config:
            config.settings = config_data.settings
        else:
            config = GlobalConfig(id=1, settings=config_data.settings)
            db.add(config)

        await db.commit()
        await db.refresh(config)
        return config
