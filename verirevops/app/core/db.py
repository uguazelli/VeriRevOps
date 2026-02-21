from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import AsyncGenerator

# Create Async Engine
engine = create_async_engine(settings.database_url, echo=False)

# Create Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# Dependency for FastAPI
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            # We don't commit here because it's up to the caller to commit if they want.
            # But we ensure it's closed and rolled back if an error occurs.
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
