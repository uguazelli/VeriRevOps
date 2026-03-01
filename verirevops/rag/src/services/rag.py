import os
import json
import logging
from typing import List, Dict, Any, Optional

from llama_index.core import Document, SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter, SemanticSplitterNodeParser
from llama_index.core.extractors import TitleExtractor, SummaryExtractor
from llama_index.core.ingestion import IngestionPipeline
from llama_index.llms.gemini import Gemini

from sqlalchemy import text

from src.core.db import get_db, get_session
from src.core.queries import INSERT_DOCUMENT_QUERY, INSERT_PARENT_DOCUMENT_QUERY
from src.core.prompts import RAG_SYSTEM_PROMPT
from src.services.embeddings import CustomGeminiEmbedding
from src.services.rerank import rerank_documents
from src.core.llm_factory import get_llm
from src.core.logging import log_start, log_success, log_error, log_llm, log_skip, log_external_call

logger = logging.getLogger(__name__)

# Single instance of embedding model
_embed_model = None

async def generate_answer(
    tenant_id: int,
    message: str,
    provider: str = "gemini"
) -> str:
    """
    Retrieves context and generates an answer using the requested LLM provider.
    """
    log_start(logger, f"Generating answer for message: '{message[:50]}...' | Provider={provider}")

    # 1. Retrieve Context
    results = await search_documents(
        tenant_id,
        message,
        use_rerank=True,
        provider=provider
    )

    if not results:
        context_str = "No relevant documents found."
    else:
        context_str = "\n\n".join([f"Source: {r['filename']}\n{r['content']}" for r in results])

    # 2. Prompt (RAG)
    prompt = RAG_SYSTEM_PROMPT.format(context_str=context_str, message=message)

    # 3. Generate
    try:
        llm = get_llm(provider)
        response = await llm.acomplete(prompt)
        answer = response.text
    except Exception as e:
        log_error(logger, f"LLM generation failed: {e}")
        answer = "Sorry, I encountered an error generating the answer."

    # 4. Log the search and answer quality
    try:
        async with get_session() as session:
            log_query = """
                INSERT INTO query_logs (tenant_id, query_text, answer_text, provider, model_name)
                VALUES (:tid, :q, :ans, :prov, :model)
            """

            # Extract basic model name string if using LlamaIndex LLM object
            model_name = getattr(llm, "model", getattr(llm, "model_name", "unknown")) if 'llm' in locals() else "unknown"

            await session.execute(
                text(log_query),
                {
                    "tid": tenant_id,
                    "q": message,
                    "ans": answer,
                    "prov": provider,
                    "model": model_name
                }
            )
            await session.commit()
    except Exception as e:
        log_error(logger, f"Failed to log query quality: {e}")

    return answer

def get_embed_model():
    """
    Factory to get the Gemini embedding model.
    """
    global _embed_model
    if _embed_model is None:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("GOOGLE_API_KEY not set.")
        logger.info("Using Google Gemini Embeddings (models/gemini-embedding-001)")
        _embed_model = CustomGeminiEmbedding(
            model_name="models/gemini-embedding-001",
            api_key=api_key
        )

    return _embed_model

from src.services.vlm import describe_image

# ... existing imports ...

async def ingest_document(tenant_id: int, filename: str, content: str = None, file_bytes: bytes = None, temp_file_path: str = None):
    """
    Parses, chunks, embeds, and inserts a document into the database.
    Supports text files (content passed), images (file_bytes passed), and physical files (temp_file_path).
    """
    logger.info(f"Ingesting document {filename} for tenant {tenant_id}")

    docs = []

    # 1. Parse File
    if temp_file_path:
        try:
            reader = SimpleDirectoryReader(input_files=[temp_file_path])
            # Load the document using the appropriate internal reader (PDF, Docx, etc)
            docs = reader.load_data()

            # Set metadata
            for doc in docs:
                doc.metadata["filename"] = filename
                doc.metadata["tenant_id"] = str(tenant_id)
                doc.metadata["original_type"] = "document"
        except Exception as e:
            logger.error(f"Error parsing document {filename}: {e}")
            return
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    else:
        # Legacy support / Fallback
        is_image = filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))

        if is_image:
            if not file_bytes:
                logger.error("Image ingestion requires file_bytes")
                return
            logger.info("Processing image with VLM...")
            content = describe_image(file_bytes, filename)
            content = f"[IMAGE DESCRIPTION for {filename}]\n{content}"

        if not content:
            logger.warning(f"No content to ingest for {filename}")
            return

        docs = [
            Document(
                text=content,
                metadata={
                    "filename": filename,
                    "tenant_id": str(tenant_id),
                    "original_type": "image" if is_image else "text"
                }
            )
        ]

    if not docs:
         logger.warning(f"No documents were loaded from {filename}")
         return

    # 2. Extract Metadata & Chunking
    llm = get_llm("gemini")
    embed_model = get_embed_model()

    pipeline = IngestionPipeline(
        transformations=[
            SemanticSplitterNodeParser(
                buffer_size=1, breakpoint_percentile_threshold=95, embed_model=embed_model
            ),
            TitleExtractor(llm=llm, nodes=5),
            SummaryExtractor(llm=llm, summaries=["prev", "self"]),
        ]
    )

    logger.info("Running Metadata Extraction Pipeline...")
    try:
        nodes = await pipeline.arun(documents=docs)
    except Exception as e:
        logger.error(f"Pipeline extraction failed: {e}")
        return

    logger.info(f"Split into {len(nodes)} chunks with Metadata")

    # 3. Embedding
    embed_model = get_embed_model()
    texts = [node.get_content() for node in nodes]

    try:
        embeddings = embed_model.get_text_embedding_batch(texts)
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return

    # 4. Insert into DB
    async with get_session() as session:
        # 4a. Insert parent document to get its ID
        # Combine possible multiple LlamaIndex Docs into one parent text
        full_content = "\n\n".join([doc.get_content() for doc in docs])
        # Use first doc's metadata as representative
        parent_meta = docs[0].metadata if docs else {}

        cursor = await session.execute(
            text(INSERT_PARENT_DOCUMENT_QUERY),
            {
                "tenant": tenant_id,
                "file": filename,
                "content": full_content,
                "meta": json.dumps(parent_meta)
            }
        )
        parent_id = cursor.scalar()

        # 4b. Insert Chunk Nodes with parent_id link
        for node, embedding in zip(nodes, embeddings):
             metadata_json = json.dumps(node.metadata)
             # using raw execute with text to ensure pgvector compatibility without full model setup
             await session.execute(
                text("INSERT INTO documents (tenant_id, filename, content, embedding, metadata_, parent_id) VALUES (:tenant, :file, :content, :emb, :meta, :pid)"),
                {
                    "tenant": tenant_id,
                    "file": filename,
                    "content": node.get_content(),
                    "emb": str(embedding),
                    "meta": metadata_json,
                    "pid": parent_id
                }
             )
        await session.commit()
    logger.info(f"Successfully ingested {filename}")

async def search_documents(
    tenant_id: int,
    message: str,
    limit: int = 5,
    use_rerank: bool = True,
    provider: str = "gemini"
) -> List[Dict[str, Any]]:
    """
    Performs a hybrid search (vector similarity + keyword search) for a message.
    Scores from both methods are merged using Reciprocal Rank Fusion (RRF).
    """
    # 1. Embed Query for Semantic Search
    search_query = message
    embed_model = get_embed_model()
    try:
        query_embedding = embed_model.get_query_embedding(search_query)
    except Exception as e:
        logger.error(f"Query embedding failed: {e}")
        return []

    # 3. Retrieve Candidates
    candidate_limit = limit * 4 if use_rerank else limit

    results = []
    async with get_session() as session:
        # Build Metadata Filter Clause
        # Simplistic implementation matching exact key-value pairs at the root of doc_metadata
        # Assumes LlamaIndex passes strings back
        metadata_filters = {} # For future expandability via function params
        filter_clause = ""
        params = {
            "emb": str(query_embedding),
            "tid": tenant_id,
            "lim": candidate_limit,
            "msg": message
        }

        if metadata_filters:
            filter_parts = []
            for i, (k, v) in enumerate(metadata_filters.items()):
                param_key = f"meta_{i}"
                # Use JSONB ->> operator to extract text value and compare
                filter_parts.append(f"metadata_->>'{k}' = :{param_key}")
                params[param_key] = str(v)

            filter_clause = " AND " + " AND ".join(filter_parts)


        # We need to run the raw SQL query. SQLAlchemy `text` takes named parameters,
        # so we will construct the text query using named parameters instead of %s
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
            params
        )
        rows = cursor.fetchall()

        for row in rows:
            results.append({
                "id": str(row.id),
                "filename": row.filename,
                "content": row.content,
                "distance": 1.0 - float(row.rrf_score) # map it logically
            })

    # 4. Reranking
    if use_rerank and results:
        logger.info(f"Reranking results with {provider}")
        results = rerank_documents(message, results, top_k=limit, provider=provider)

    return results


