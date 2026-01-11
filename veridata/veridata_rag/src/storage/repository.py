import logging
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from src.storage.db import get_db

logger = logging.getLogger(__name__)

def get_tenant_languages(tenant_id: UUID) -> Optional[str]:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT preferred_languages FROM tenants WHERE id = %s", (tenant_id,))
                res = cur.fetchone()
                return res[0] if res and res[0] else None
    except Exception as e:
        logger.error(f"Failed to fetch tenant languages: {e}")
        return None

def insert_document_chunk(
    tenant_id: UUID,
    filename: str,
    content: str,
    embedding: List[float]
) -> bool:
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents (tenant_id, filename, content, embedding, fts_vector)
                    VALUES (%s, %s, %s, %s, to_tsvector('english', %s))
                    """,
                    (tenant_id, filename, content, embedding, content)
                )
        return True
    except Exception as e:
        logger.error(f"Failed to insert document chunk for {filename}: {e}")
        return False

def search_documents_hybrid(
    tenant_id: UUID,
    query_embedding: List[float],
    query_text: str,
    limit: int
) -> List[Dict[str, Any]]:
    results = []
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                # Hybrid search with RRF (Reciprocal Rank Fusion)
                cur.execute(
                    """
                    WITH vector_search AS (
                        SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> %s::vector) as rank
                        FROM documents
                        WHERE tenant_id = %s
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                    ),
                    keyword_search AS (
                        SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(fts_vector, websearch_to_tsquery('english', %s)) DESC) as rank
                        FROM documents
                        WHERE tenant_id = %s AND fts_vector @@ websearch_to_tsquery('english', %s)
                        LIMIT %s
                    )
                    SELECT
                        d.id, d.filename, d.content,
                        COALESCE(1.0 / (vs.rank + 60), 0.0) + COALESCE(1.0 / (ks.rank + 60), 0.0) as score
                    FROM documents d
                    LEFT JOIN vector_search vs ON d.id = vs.id
                    LEFT JOIN keyword_search ks ON d.id = ks.id
                    WHERE vs.id IS NOT NULL OR ks.id IS NOT NULL
                    ORDER BY score DESC
                    LIMIT %s;
                    """,
                    (query_embedding, tenant_id, query_embedding, limit,
                     query_text, tenant_id, query_text, limit,
                     limit)
                )
                rows = cur.fetchall()

                for row in rows:
                    results.append({
                        "id": str(row[0]),
                        "filename": row[1],
                        "content": row[2],
                        "score": float(row[3])
                    })
    except Exception as e:
        logger.error(f"Hybrid search failed: {e}")

    return results
