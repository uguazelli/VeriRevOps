import asyncio
import logging

from sqlalchemy import text

from bot.core.db import engine

# Import all models to ensure they are registered with Base.metadata
from bot.models.base import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_db():
    logger.info("Creating database tables...")
    async with engine.begin() as conn:
        logger.info("Enabling vector extension...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

        # MIGRATION: Ensure updated_at exists on global_configs
        try:
            logger.info("Ensuring 'updated_at' column exists on 'global_configs'...")
            await conn.execute(text("ALTER TABLE global_configs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"))
        except Exception as e:
            logger.warning(f"Migration check failed (safe to ignore if column exists): {e}")

    logger.info("Tables created successfully.")

if __name__ == "__main__":
    asyncio.run(init_db())
