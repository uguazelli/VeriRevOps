"""
Central repository for all raw SQL queries.
"""

HYBRID_DOCUMENT_SEARCH_QUERY = """
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

INSERT_PARENT_DOCUMENT_QUERY = """
INSERT INTO documents (tenant_id, filename, content, metadata_)
VALUES (:tenant, :file, :content, :meta)
RETURNING id;
"""

INSERT_CHILD_DOCUMENT_QUERY = """
INSERT INTO documents (tenant_id, filename, content, embedding, metadata_, parent_id)
VALUES (:tenant, :file, :content, :emb, :meta, :pid)
"""
