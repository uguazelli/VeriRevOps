import asyncpg
from contextlib import asynccontextmanager
from app.config import settings

pool: asyncpg.Pool | None = None

async def init_db_pool():
    global pool
    pool = await asyncpg.create_pool(dsn=settings.DATABASE_URL)

async def close_db_pool():
    global pool
    if pool:
        await pool.close()

async def get_db_pool() -> asyncpg.Pool:
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool

@asynccontextmanager
async def get_db_connection():
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    async with pool.acquire() as connection:
        yield connection
