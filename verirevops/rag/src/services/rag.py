import os
import logging
from typing import List, Dict, Any, Optional
from uuid import UUID

from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.llms.gemini import Gemini

from src.core.db import get_db
from src.services.embeddings import CustomGeminiEmbedding
from src.services.rerank import rerank_documents
from src.core.llm_factory import get_llm
from src.core.logging import log_start, log_success, log_error, log_llm, log_skip, log_external_call

logger = logging.getLogger(__name__)

# Single instance of embedding model
_embed_model = None

def generate_answer(
    tenant_id: int,
    message: str,
    provider: str = "gemini"
) -> str:
    """
    Retrieves context and generates an answer using the requested LLM provider.
    """
    log_start(logger, f"Generating answer for message: '{message[:50]}...' | Provider={provider}")

    # 1. Retrieve Context
    results = search_documents(
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
    prompt = (
        "You are Veribot 🤖, an AI assistant.\n"
        "Use the following pieces of retrieved context to answer the user's question.\n"
        "IMPORTANT: Always answer in the same language as the user's question.\n"
        "If asked about your identity, say you are Veribot 🤖, an AI assistant capable of answering most questions and redirecting to a human if needed.\n"
        "Priority: Use the retrieved context for factual information about the documents.\n"
        "If the answer is not in the context, say you don't know.\n\n"
        f"Retrieved Context:\n{context_str}\n\n"
        f"Question: {message}\n\n"
        "Answer:"
    )

    # 3. Generate
    try:
        llm = get_llm(provider)
        response = llm.complete(prompt)
        answer = response.text
    except Exception as e:
        log_error(logger, f"LLM generation failed: {e}")
        answer = "Sorry, I encountered an error generating the answer."

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

def ingest_document(tenant_id: int, filename: str, content: str = None, file_bytes: bytes = None):
    """
    Parses, chunks, embeds, and inserts a document into the database.
    Supports text files (content passed) and images (file_bytes passed).
    """
    logger.info(f"Ingesting document {filename} for tenant {tenant_id}")

    # 0. Handle Images (Multimodal)
    is_image = filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))

    if is_image:
        if not file_bytes:
            logger.error("Image ingestion requires file_bytes")
            return
        logger.info("Processing image with VLM...")
        # Overwrite content with the image description
        content = describe_image(file_bytes, filename)
        # We can prepend a tag so we know it's an image description
        content = f"[IMAGE DESCRIPTION for {filename}]\n{content}"

    if not content:
        logger.warning(f"No content to ingest for {filename}")
        return

    # 1. Create LlamaIndex Document
    doc = Document(
        text=content,
        metadata={
            "filename": filename,
            "tenant_id": str(tenant_id),
            "original_type": "image" if is_image else "text"
        }
    )

    # 2. Chunking
    splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=20)
    nodes = splitter.get_nodes_from_documents([doc])

    logger.info(f"Split into {len(nodes)} chunks")

    # 3. Embedding
    embed_model = get_embed_model()
    texts = [node.get_content() for node in nodes]

    try:
        embeddings = embed_model.get_text_embedding_batch(texts)
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return

    # 4. Insert into DB
    with get_db() as conn:
        with conn.cursor() as cur:
            for node, embedding in zip(nodes, embeddings):
                cur.execute(
                    """
                    INSERT INTO documents (tenant_id, filename, content, embedding)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (tenant_id, filename, node.get_content(), embedding)
                )
    logger.info(f"Successfully ingested {filename}")

def search_documents(
    tenant_id: int,
    message: str,
    limit: int = 5,
    use_rerank: bool = True,
    provider: str = "gemini"
) -> List[Dict[str, Any]]:
    """
    Performs a hybrid search (currently vector similarity) for a message.
    Supports Reranking.
    """
    # 1. Embed Query
    search_query = message
    embed_model = get_embed_model()
    try:
        query_embedding = embed_model.get_query_embedding(search_query)
    except Exception as e:
        logger.error(f"Query embedding failed: {e}")
        return []

    # 3. Retrieve Candidates
    # If using rerank, we fetch more candidates (e.g., 4x the limit) to rerank down
    candidate_limit = limit * 4 if use_rerank else limit

    results = []
    with get_db() as conn:
        with conn.cursor() as cur:
            # Vector search with Cosine Similarity (<=> operator)
            # Ordered by distance ASC (closest first)
            cur.execute(
                """
                SELECT id, filename, content, (embedding <=> %s::vector) as distance
                FROM documents
                WHERE tenant_id = %s
                ORDER BY distance ASC
                LIMIT %s
                """,
                (query_embedding, tenant_id, candidate_limit)
            )
            rows = cur.fetchall()

            for row in rows:
                results.append({
                    "id": str(row[0]),
                    "filename": row[1],
                    "content": row[2],
                    "distance": float(row[3])
                })

    # 4. Reranking
    if use_rerank and results:
        logger.info(f"Reranking results with {provider}")
        # We rerank against the ORIGINAL message
        results = rerank_documents(message, results, top_k=limit, provider=provider)

    return results


