import logging
import os
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager

import psycopg
from psycopg_pool import ConnectionPool
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.core.schema_queries import SCHEMA_BOOTSTRAP_QUERIES, SCHEMA_INDEX_QUERIES

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None
_engine: AsyncEngine | None = None
_SessionLocal: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    global _SessionLocal

    if _engine is None:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL environment variable is not set")

        # SQLAlchemy 2.0 with psycopg v3 requires the +psycopg dialect
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

        _engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
        _SessionLocal = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)

    return _engine


def get_pool() -> ConnectionPool:
    global _pool

    if _pool is None:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL environment variable is not set")
        _pool = ConnectionPool(conninfo=db_url, min_size=1, max_size=10)

    return _pool


@contextmanager
def get_db() -> Generator[psycopg.Connection, None, None]:
    """Get a database connection from the pool."""
    pool = get_pool()
    with pool.connection() as conn:
        yield conn


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an asynchronous SQLAlchemy ORM session."""
    get_engine()

    if _SessionLocal is None:
        raise RuntimeError("Database session factory is not configured")

    async with _SessionLocal() as session:
        yield session


def init_db():
    """Initialize the database schema."""
    logger.info("Initializing database schema...")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL environment variable is not set. Skipping DB Init.")
        return

    # To run synchronous setup scripts, we can use an ephemeral synchronous psycopg connection
    db_url_sync = db_url.replace("postgresql+psycopg://", "postgresql://", 1)

    with psycopg.connect(conninfo=db_url_sync) as conn:
        with conn.cursor() as cur:
            for query in SCHEMA_BOOTSTRAP_QUERIES:
                cur.execute(query)

            for query in SCHEMA_INDEX_QUERIES:
                cur.execute(query)

            conn.commit()

    logger.info("Database schema initialized.")


def close_pool():
    global _pool

    if _pool is not None:
        _pool.close()
        _pool = None
