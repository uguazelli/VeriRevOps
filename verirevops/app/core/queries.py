
CREATE_TENANTS_TABLE = """
    CREATE TABLE IF NOT EXISTS tenants (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        url TEXT NOT NULL,
        is_active BOOLEAN DEFAULT TRUE
    );
"""

CREATE_SUBSCRIPTIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS subscriptions (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER REFERENCES tenants(id),
        quota_limit INTEGER,
        usage_count INTEGER DEFAULT 0,
        start_date TIMESTAMP,
        end_date TIMESTAMP
    );
"""

CREATE_CHAT_SESSIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER REFERENCES tenants(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
"""

CREATE_CHAT_MESSAGES_TABLE = """
    CREATE TABLE IF NOT EXISTS chat_messages (
        id SERIAL PRIMARY KEY,
        session_id INTEGER REFERENCES chat_sessions(id),
        content TEXT NOT NULL,
        role TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
"""

# --- Admin Queries ---

# Tenants
GET_ALL_TENANTS = "SELECT id, name, slug, url, is_active FROM tenants ORDER BY id"
CREATE_TENANT = "INSERT INTO tenants (name, slug, url, is_active) VALUES (%s, %s, %s, %s) RETURNING id"
UPDATE_TENANT = "UPDATE tenants SET name = %s, slug = %s, url = %s, is_active = %s WHERE id = %s"
DELETE_TENANT = "DELETE FROM tenants WHERE id = %s"
GET_TENANT_NAME_BY_ID = "SELECT name FROM tenants WHERE id = %s"

# Subscriptions
GET_ALL_SUBSCRIPTIONS = """
    SELECT s.id, s.tenant_id, s.quota_limit, s.usage_count, s.start_date, s.end_date, t.name
    FROM subscriptions s
    LEFT JOIN tenants t ON s.tenant_id = t.id
    ORDER BY s.id
"""
CREATE_SUBSCRIPTION = "INSERT INTO subscriptions (tenant_id, quota_limit, usage_count, start_date, end_date) VALUES (%s, %s, %s, %s, %s) RETURNING id"
UPDATE_SUBSCRIPTION = "UPDATE subscriptions SET tenant_id = %s, quota_limit = %s, usage_count = %s, start_date = %s, end_date = %s WHERE id = %s"
DELETE_SUBSCRIPTION = "DELETE FROM subscriptions WHERE id = %s"

# Chat Sessions
GET_ALL_CHAT_SESSIONS = """
    SELECT s.id, s.tenant_id, s.created_at, t.name
    FROM chat_sessions s
    LEFT JOIN tenants t ON s.tenant_id = t.id
    ORDER BY s.id DESC
"""
CREATE_CHAT_SESSION = "INSERT INTO chat_sessions (tenant_id) VALUES (%s) RETURNING id, created_at"
UPDATE_CHAT_SESSION = "UPDATE chat_sessions SET tenant_id = %s WHERE id = %s RETURNING created_at"
DELETE_CHAT_SESSION = "DELETE FROM chat_sessions WHERE id = %s"

# Chat Messages
GET_CHAT_MESSAGES_BASE = """
    SELECT m.id, m.session_id, m.content, m.role, m.created_at, t.name
    FROM chat_messages m
    JOIN chat_sessions s ON m.session_id = s.id
    LEFT JOIN tenants t ON s.tenant_id = t.id
"""

# --- RAG Tables ---

CREATE_RAG_FILES_TABLE = """
    CREATE TABLE IF NOT EXISTS rag_files (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER REFERENCES tenants(id),
        filename TEXT NOT NULL,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
"""

CREATE_RAG_CHUNKS_TABLE = """
    CREATE TABLE IF NOT EXISTS rag_chunks (
        id SERIAL PRIMARY KEY,
        file_id INTEGER REFERENCES rag_files(id) ON DELETE CASCADE,
        chunk_index INTEGER NOT NULL,
        content TEXT NOT NULL,
        embedding vector(1536),
        metadata JSONB DEFAULT '{}'
    );
"""

# --- RAG Queries ---

# Files
GET_RAG_FILES_BY_TENANT = "SELECT id, filename, uploaded_at FROM rag_files WHERE tenant_id = %s ORDER BY uploaded_at DESC"
INSERT_RAG_FILE = "INSERT INTO rag_files (tenant_id, filename) VALUES (%s, %s) RETURNING id"
DELETE_RAG_FILE = "DELETE FROM rag_files WHERE id = %s"
GET_RAG_FILE_BY_ID = "SELECT * FROM rag_files WHERE id = %s"

# Chunks
INSERT_RAG_CHUNK = "INSERT INTO rag_chunks (file_id, chunk_index, content, embedding, metadata) VALUES (%s, %s, %s, %s, %s) RETURNING id"
DELETE_CHUNKS_BY_FILE = "DELETE FROM rag_chunks WHERE file_id = %s"

# Vector Search
# Uses cosine distance (<=>) for similarity search
SEARCH_SIMILAR_CHUNKS = """
    SELECT content, metadata, 1 - (embedding <=> %s) AS similarity
    FROM rag_chunks
    WHERE file_id IN (SELECT id FROM rag_files WHERE tenant_id = %s)
    ORDER BY embedding <=> %s
    LIMIT %s
"""
