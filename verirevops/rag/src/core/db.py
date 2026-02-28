import os
import logging
from contextlib import contextmanager
from typing import Generator
import psycopg
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

# Singleton pool
_pool: ConnectionPool = None

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

def init_db():
    """Initialize the database schema."""
    logger.info("Initializing database schema...")
    with get_db() as conn:
        with conn.cursor() as cur:
            # Enable pgvector extension
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

            # Create tenants table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tenants (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    slug VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Migration: Rename name to slug if it exists
            cur.execute("""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name='tenants' AND column_name='name'
                    ) THEN
                        ALTER TABLE tenants RENAME COLUMN name TO slug;
                    END IF;
                END $$;
            """)


            # Create documents table
            # embedding vector size depends on provider
            dim = 3072

            # Check existing dimension if table exists
            cur.execute("SELECT to_regclass('documents');")
            if cur.fetchone()[0]:
                cur.execute("""
                    SELECT atttypmod
                    FROM pg_attribute
                    WHERE attrelid = 'documents'::regclass
                    AND attname = 'embedding';
                """)
                res = cur.fetchone()
                if res:
                    current_dim = res[0]
                    if current_dim != dim:
                        logger.warning(f"Embedding dimension mismatch (Current: {current_dim}, Expected: {dim}). "
                                       "Dropping documents table to recreate with correct dimension.")
                        cur.execute("DROP TABLE documents CASCADE;")

            logger.info(f"Creating documents table with vector dimension: {dim} (Provider: Gemini)")

            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS documents (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
                    filename VARCHAR(255) NOT NULL,
                    content TEXT NOT NULL,
                    embedding vector({dim}),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Create index for tenant_id for faster filtering
            cur.execute("""
                CREATE INDEX IF NOT EXISTS documents_tenant_id_idx ON documents (tenant_id);
            """)

            # Create index for tenant_id for faster filtering
            cur.execute("""
                CREATE INDEX IF NOT EXISTS documents_tenant_id_idx ON documents (tenant_id);
            """)

    logger.info("Database schema initialized.")

def close_pool():
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
