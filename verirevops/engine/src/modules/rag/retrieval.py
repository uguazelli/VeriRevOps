import asyncio
import logging
from typing import Any

from sqlalchemy import text

from src.core.db import get_session
from src.core.queries import HYBRID_DOCUMENT_SEARCH_QUERY
from src.modules.rag.embeddings import get_embed_model
from src.modules.rag.reranking import rerank_documents


logger = logging.getLogger(__name__)


async def search_documents(
    tenant_id: int,
    message: str,
    limit: int = 5,
    use_rerank: bool = True,
    provider: str = "gemini",
) -> list[dict[str, Any]]:
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

        raw_query = HYBRID_DOCUMENT_SEARCH_QUERY.format(filter_clause=filter_clause)

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
