import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from bot.core.db import get_session

logger = logging.getLogger(__name__)


async def get_client_languages(client_id: int) -> Optional[str]:
    # Placeholder: In the future we might want to store languages in Client model or Configs
    # For now, return None or query if we add a column.
    # The Client model doesn't have preferred_languages yet.
    # We can default to "Portuguese/English" or ignore.
    return "Portuguese, English"


async def insert_document_chunk(
    client_id: int, filename: str, content: str, embedding: List[float]
) -> bool:
    async for session in get_session():
        try:
            # We use direct SQL for insertion to leverage to_tsvector easily without triggers,
            # mirroring the logic from the RAG service but adapted for client_id.

            stmt = text("""
                INSERT INTO documents (client_id, filename, content, embedding, fts_vector)
                VALUES (:client_id, :filename, :content, :embedding, to_tsvector('english', :content))
            """)
            await session.execute(
                stmt,
                {
                    "client_id": client_id,
                    "filename": filename,
                    "content": content,
                    "embedding": str(embedding), # pgvector cast
                },
            )
            await session.commit()
            return True
        except Exception as e:
            print(f"DEBUG: DB INSERT ERROR: {e}", flush=True)
            logger.error(f"Failed to insert document chunk for {filename}: {e}")
            return False


async def search_documents_hybrid(
    client_id: int, query_embedding: List[float], query_text: str, limit: int
) -> List[Dict[str, Any]]:
    results = []
    async for session in get_session():
        try:
            # Hybrid search with RRF (Reciprocal Rank Fusion)
            stmt = text("""
                WITH vector_search AS (
                    SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> :embedding) as rank
                    FROM documents
                    WHERE client_id = :client_id
                    ORDER BY embedding <=> :embedding
                    LIMIT :limit
                ),
                keyword_search AS (
                    SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(fts_vector, websearch_to_tsquery('english', :query_text)) DESC) as rank
                    FROM documents
                    WHERE client_id = :client_id AND fts_vector @@ websearch_to_tsquery('english', :query_text)
                    LIMIT :limit
                )
                SELECT
                    d.id, d.filename, d.content,
                    COALESCE(1.0 / (vs.rank + 60), 0.0) + COALESCE(1.0 / (ks.rank + 60), 0.0) as score
                FROM documents d
                LEFT JOIN vector_search vs ON d.id = vs.id
                LEFT JOIN keyword_search ks ON d.id = ks.id
                WHERE vs.id IS NOT NULL OR ks.id IS NOT NULL
                ORDER BY score DESC
                LIMIT :limit;
            """)

            result = await session.execute(
                stmt,
                {
                    "embedding": str(query_embedding),
                    "client_id": client_id,
                    "limit": limit,
                    "query_text": query_text,
                },
            )

            rows = result.fetchall()

            for row in rows:
                results.append(
                    {
                        "id": str(row[0]),
                        "filename": row[1],
                        "content": row[2],
                        "score": float(row[3]),
                    }
                )
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")

    return results
