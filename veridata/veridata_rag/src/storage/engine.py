import os
import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Ensure using async driver
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session



async def dispose_engine():
    await engine.dispose()


async def ensure_database_exists():
    import psycopg
    from urllib.parse import urlparse

    parsed = urlparse(DATABASE_URL)
    db_name = parsed.path.lstrip("/")

    if not db_name:
        logger.warning("No database name found in DATABASE_URL")
        return

    # Construct connection string for 'postgres' database
    user = parsed.username
    password = parsed.password
    host = parsed.hostname
    port = parsed.port or 5432

    # Reconstruct robust conn string or use param dict
    conn_info = f"dbname=postgres user={user} password={password} host={host} port={port}"

    try:
        # Autocommit is required for CREATE DATABASE
        async with await psycopg.AsyncConnection.connect(conn_info, autocommit=True) as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
                if not await cur.fetchone():
                    logger.info(f"Database '{db_name}' does not exist. Creating...")
                    await cur.execute(f'CREATE DATABASE "{db_name}"')
                    logger.info(f"Database '{db_name}' created successfully.")
                else:
                    logger.debug(f"Database '{db_name}' already exists.")
    except Exception as e:
        logger.error(f"Failed to check/create database '{db_name}': {e}")


async def run_migrations():
    from alembic import command
    from alembic.config import Config

    logger.info("Running database migrations...")
    try:
        # Assume alembic.ini is in the service root (2 levels up from src/storage)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        alembic_cfg_path = os.path.join(base_dir, "alembic.ini")

        if not os.path.exists(alembic_cfg_path):
            raise FileNotFoundError(f"alembic.ini not found at {alembic_cfg_path}")

        alembic_cfg = Config(alembic_cfg_path)

        # Execute upgrade synchronously (it creates its own connection/engine in env.py)
        command.upgrade(alembic_cfg, "head")

        logger.info("Database migrations completed successfully.")
    except Exception as e:
        logger.error(f"Failed to run migrations: {e}")
        raise e
