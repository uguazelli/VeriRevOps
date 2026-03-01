"""
Central repository for all raw SQL queries.
"""

HYBRID_SEARCH_QUERY = """
WITH vector_search AS (
    SELECT id, filename, content,
           (embedding <=> %s::vector) as distance,
           ROW_NUMBER() OVER(ORDER BY (embedding <=> %s::vector) ASC) as rank
    FROM documents
    WHERE tenant_id = %s
    ORDER BY distance ASC
    LIMIT %s
),
keyword_search AS (
    SELECT id, filename, content,
           ts_rank(fts, websearch_to_tsquery('english', %s)) as rank_score,
           ROW_NUMBER() OVER(ORDER BY ts_rank(fts, websearch_to_tsquery('english', %s)) DESC) as rank
    FROM documents
    WHERE tenant_id = %s
      AND fts @@ websearch_to_tsquery('english', %s)
    ORDER BY rank_score DESC
    LIMIT %s
)
SELECT
    COALESCE(v.id, k.id) as id,
    COALESCE(v.filename, k.filename) as filename,
    COALESCE(v.content, k.content) as content,
    COALESCE(1.0 / (60 + v.rank), 0.0) +
    COALESCE(1.0 / (60 + k.rank), 0.0) as rrf_score
FROM vector_search v
FULL OUTER JOIN keyword_search k ON v.id = k.id
ORDER BY rrf_score DESC
LIMIT %s;
"""

INSERT_DOCUMENT_QUERY = """
INSERT INTO documents (tenant_id, filename, content, embedding, metadata_, parent_id)
VALUES (%s, %s, %s, %s, %s, %s)
"""

INSERT_PARENT_DOCUMENT_QUERY = """
INSERT INTO documents (tenant_id, filename, content, metadata_)
VALUES (:tenant, :file, :content, :meta)
RETURNING id;
"""
