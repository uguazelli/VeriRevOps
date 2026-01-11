import os
import logging
from typing import List, Dict, Any, Optional
from uuid import UUID
from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from src.services.embeddings import CustomGeminiEmbedding
from src.config.logging import log_start, log_error, log_skip
from src.storage.repository import insert_document_chunk
from src.services.vlm import describe_image
from src.services.vlm import describe_image
from src.utils.prompts import (
    RAG_ANSWER_PROMPT_TEMPLATE,
    SMALL_TALK_PROMPT_TEMPLATE
)
from src.services.rag_flow import (
    get_embed_model,
    resolve_config,
    get_language_instruction,
    prepare_query_context,
    determine_intent,
    retrieve_context,
    generate_llm_response,
    save_interaction
)

logger = logging.getLogger(__name__)

# --- Ingestion Service ---

def ingest_document(tenant_id: UUID, filename: str, content: str = None, file_bytes: bytes = None):
    logger.info(f"Ingesting document {filename} for tenant {tenant_id}")

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

    # 4. Insert into DB (Delegated to Repository)
    for node, embedding in zip(nodes, embeddings):
        success = insert_document_chunk(tenant_id, filename, node.get_content(), embedding)
        if not success:
            logger.error(f"Failed to insert chunk for {filename}")

    logger.info(f"Successfully ingested {filename}")

# --- Generation Service ---

def generate_answer(
    tenant_id: UUID,
    query: str,
    use_hyde: Optional[bool] = None,
    use_rerank: Optional[bool] = None,
    provider: Optional[str] = None,
    session_id: Optional[UUID] = None,
    complexity_score: int = 5,
    pricing_intent: bool = False,
    external_context: Optional[str] = None
) -> tuple[str, bool]:

    log_start(logger, f"Generating answer for query: '{query}'")

    # 1. Config
    use_hyde, use_rerank = resolve_config(use_hyde, use_rerank)
    lang_instruction = get_language_instruction(tenant_id)

    # 2. Contextualization
    search_query, history = prepare_query_context(session_id, query, provider)
    history_str = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in history]) if history else ""

    # 3. Intent & Routing
    requires_rag, gen_step = determine_intent(complexity_score, pricing_intent)

    # 4. Execution Flow
    answer = ""
    if requires_rag:
        context_str, final_lang_instruction = retrieve_context(
            tenant_id, search_query, external_context, use_hyde, use_rerank, provider, lang_instruction
        )
        answer = generate_llm_response(
            prompt_template=RAG_ANSWER_PROMPT_TEMPLATE,
            template_args={
                "lang_instruction": final_lang_instruction,
                "history_str": history_str,
                "context_str": context_str,
                "search_query": search_query
            },
            gen_step=gen_step,
            provider=provider
        )
    else:
        # Small Talk
        log_skip(logger, "Small talk detected. Bypassing RAG.")
        answer = generate_llm_response(
            prompt_template=SMALL_TALK_PROMPT_TEMPLATE,
            template_args={
                "lang_instruction": lang_instruction,
                "history_str": history_str,
                "search_query": search_query
            },
            gen_step=gen_step,
            provider=provider
        )

    # 5. Persistence
    save_interaction(session_id, query, answer)

    # Compatibility return (answer, references_used_bool)
    return answer, False


def ingest_document(tenant_id: UUID, filename: str, content: str = None, file_bytes: bytes = None):
    logger.info(f"Ingesting document {filename} for tenant {tenant_id}")

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

    # 4. Insert into DB (Delegated to Repository)
    for node, embedding in zip(nodes, embeddings):
        success = insert_document_chunk(tenant_id, filename, node.get_content(), embedding)
        if not success:
            logger.error(f"Failed to insert chunk for {filename}")

    logger.info(f"Successfully ingested {filename}")

def search_documents(
    tenant_id: UUID,
    query: str,
    limit: int = 5,
    use_hyde: bool = False,
    use_rerank: bool = False,
    provider: str = "gemini"
) -> List[Dict[str, Any]]:

    search_query = query
    if use_hyde:
        logger.info(f"🔍 Opt 1 (Accuracy): Using HyDE expansion with {provider}")
        search_query = generate_hypothetical_answer(query, provider=provider)

    # 2. Embed Query
    embed_model = get_embed_model()
    try:
        query_embedding = embed_model.get_query_embedding(search_query)
    except Exception as e:
        logger.error(f"Query embedding failed: {e}")
        return []

    # 3. Retrieve Candidates (Delegated to Repository)
    # If using rerank, we fetch more candidates (e.g., 4x the limit) to rerank down
    candidate_limit = limit * 4 if use_rerank else limit

    logger.info(f"🔍 Opt 2 (Accuracy): Performing Hybrid Search (Vector + FTS) with RRF (Limit: {candidate_limit})")

    results = search_documents_hybrid(tenant_id, query_embedding, query, candidate_limit)

    # 4. Reranking
    if use_rerank and results:
        logger.info(f"Reranking results with {provider}")
        # We rerank against the ORIGINAL query, not the HyDE query
        results = rerank_documents(query, results, top_k=limit, provider=provider)

    return results


