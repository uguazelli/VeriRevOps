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
    pool = get_pool()
    with pool.connection() as conn:
        yield conn

def init_db():
    logger.info("Initializing database schema...")
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS tenants (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    preferred_languages TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS global_configs (
                    id SERIAL PRIMARY KEY,
                    config JSONB NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            try:
                cur.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS preferred_languages TEXT;")
            except Exception as e:
                logger.warning(f"Migration check for preferred_languages failed: {e}")

            dim = 768
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
                    fts_vector tsvector,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            try:
                cur.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS fts_vector tsvector;")
                cur.execute("CREATE INDEX IF NOT EXISTS documents_fts_vector_idx ON documents USING GIN (fts_vector);")
                cur.execute("UPDATE documents SET fts_vector = to_tsvector('english', content) WHERE fts_vector IS NULL;")
            except Exception as e:
                logger.warning(f"Migration check for fts_vector failed: {e}")

            cur.execute("""
                CREATE INDEX IF NOT EXISTS documents_embedding_idx
                ON documents
                USING hnsw (embedding vector_cosine_ops);
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS documents_tenant_id_idx ON documents (tenant_id);
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
                    role VARCHAR(50) NOT NULL, -- 'user' or 'ai'
                    content TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS chat_messages_session_id_idx ON chat_messages (session_id);
            """)
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS query_cache (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
                    query_text TEXT NOT NULL,
                    embedding vector({dim}),
                    answer_text TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS query_cache_embedding_idx
                ON query_cache
                USING hnsw (embedding vector_cosine_ops);
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS query_cache_tenant_id_idx ON query_cache (tenant_id);
            """)

    logger.info("Database schema initialized.")

def close_pool():
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
