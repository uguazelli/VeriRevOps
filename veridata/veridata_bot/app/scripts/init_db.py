import asyncio
import logging
from sqlalchemy import text

from app.core.db import engine
from app.models.base import Base
# Import all models to ensure they are registered with Base.metadata
from app.models import Client, BotSession, Subscription, ServiceConfig
from app.rag.models.sql import Document, ChatSession, ChatMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_db():
    logger.info("Creating database tables...")
    async with engine.begin() as conn:
        logger.info("Enabling vector extension...")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Tables created successfully.")

if __name__ == "__main__":
    asyncio.run(init_db())
