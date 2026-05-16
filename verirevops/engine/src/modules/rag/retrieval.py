import asyncio
import logging
from typing import Any, Dict, List

from sqlalchemy import text

from src.core.db import get_session
from src.modules.rag.embeddings import get_embed_model
from src.modules.rag.reranking import rerank_documents


logger = logging.getLogger(__name__)


async def search_documents(
    tenant_id: int,
    message: str,
    limit: int = 5,
    use_rerank: bool = True,
    provider: str = "gemini",
) -> List[Dict[str, Any]]:
    """
    Performs hybrid search: vector similarity plus keyword search.
    """
    embed_model = get_embed_model()
    try:
        query_embedding = await asyncio.to_thread(
            embed_model.get_query_embedding,
            message,
        )
    except Exception as exc:
        logger.error("Query embedding failed: %s", exc)
        return []

    candidate_limit = limit * 4 if use_rerank else limit

    results = []
    async with get_session() as session:
        metadata_filters = {}
        filter_clause = ""
        params = {
            "emb": str(query_embedding),
            "tid": tenant_id,
            "lim": candidate_limit,
            "msg": message,
        }

        if metadata_filters:
            filter_parts = []
            for index, (key, value) in enumerate(metadata_filters.items()):
                param_key = f"meta_{index}"
                filter_parts.append(f"metadata_->>'{key}' = :{param_key}")
                params[param_key] = str(value)

            filter_clause = " AND " + " AND ".join(filter_parts)

        raw_query = f"""
                WITH vector_search AS (
                    SELECT id, parent_id, filename, content,
                           (embedding <=> CAST(:emb AS vector)) as distance,
                           ROW_NUMBER() OVER(ORDER BY (embedding <=> CAST(:emb AS vector)) ASC) as rank
                    FROM documents
                    WHERE tenant_id = :tid AND embedding IS NOT NULL {filter_clause}
                    ORDER BY distance ASC
                    LIMIT :lim
                ),
                keyword_search AS (
                    SELECT id, parent_id, filename, content,
                           ts_rank(fts, websearch_to_tsquery('english', :msg)) as rank_score,
                           ROW_NUMBER() OVER(ORDER BY ts_rank(fts, websearch_to_tsquery('english', :msg)) DESC) as rank
                    FROM documents
                    WHERE tenant_id = :tid AND embedding IS NOT NULL {filter_clause}
                      AND fts @@ websearch_to_tsquery('english', :msg)
                    ORDER BY rank_score DESC
                    LIMIT :lim
                ),
                combined_chunks AS (
                    SELECT
                        COALESCE(v.parent_id, k.parent_id, v.id, k.id) as target_doc_id,
                        COALESCE(1.0 / (60 + v.rank), 0.0) +
                        COALESCE(1.0 / (60 + k.rank), 0.0) as rrf_score
                    FROM vector_search v
                    FULL OUTER JOIN keyword_search k ON v.id = k.id
                ),
                ranked_parents AS (
                    SELECT target_doc_id, MAX(rrf_score) as best_score
                    FROM combined_chunks
                    GROUP BY target_doc_id
                    ORDER BY best_score DESC
                    LIMIT :lim
                )
                SELECT
                    p.id,
                    p.filename,
                    p.content,
                    rp.best_score as rrf_score
                FROM ranked_parents rp
                JOIN documents p ON rp.target_doc_id = p.id;
        """

        cursor = await session.execute(
            text(raw_query),
            params,
        )
        rows = cursor.fetchall()

        for row in rows:
            results.append({
                "id": str(row.id),
                "filename": row.filename,
                "content": row.content,
                "distance": 1.0 - float(row.rrf_score),
            })

    if use_rerank and results:
        logger.info("Reranking results with %s", provider)
        results = await asyncio.to_thread(
            rerank_documents,
            message,
            results,
            top_k=limit,
            provider=provider,
        )

    return results
