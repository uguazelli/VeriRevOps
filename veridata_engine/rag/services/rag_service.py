import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from langchain_core.prompts import PromptTemplate
from langchain_core.prompts import PromptTemplate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import settings
from bot.core.db import async_session_maker
from bot.services.global_config_service import get_llm_config
from rag.models.sql import ChatMessage, ChatSession
from rag.storage.repository import search_documents_hybrid
from utils.prompts import (
    CONTEXTUALIZE_PROMPT_TEMPLATE,
    HYDE_PROMPT_TEMPLATE,
    RAG_ANSWER_PROMPT_TEMPLATE,
    RERANK_PROMPT_TEMPLATE,
    SMALL_TALK_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)


from bot.core.ai import get_llm, get_embeddings


async def get_chat_history(session_id: UUID, limit: int = 5) -> List[Dict[str, str]]:
    history = []
    async with async_session_maker() as session:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        messages = result.scalars().all()

        # Reverse to chronological order
        for msg in reversed(messages):
            history.append({"role": msg.role, "content": msg.content})
    return history


async def contextualize_query(query: str, history: List[Dict[str, str]]) -> str:
    if not history:
        return query

    history_str = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in history])

    # Fetch dynamic config
    config = await get_llm_config()
    model_name = config["steps"]["contextualization"]["model"]

    llm = get_llm(model_name=model_name)
    prompt = PromptTemplate.from_template(CONTEXTUALIZE_PROMPT_TEMPLATE)
    chain = prompt | llm

    try:
        response = await chain.ainvoke({"history_str": history_str, "query": query})
        rewritten = response.content.strip()
        logger.info(f"Contextualized: '{query}' -> '{rewritten}'")
        return rewritten
    except Exception as e:
        logger.error(f"Contextualization failed: {e}")
        return query


async def generate_hypothetical_answer(query: str) -> str:
    # Fetch dynamic config
    config = await get_llm_config()
    model_name = config["steps"]["rag_search"]["model"]

    llm = get_llm(model_name=model_name)
    prompt = PromptTemplate.from_template(HYDE_PROMPT_TEMPLATE)
    chain = prompt | llm
    try:
        response = await chain.ainvoke({"query": query})
        hypothetical = response.content.strip()
        logger.info(f"HyDE generated: {hypothetical[:100]}...")
        return hypothetical
    except Exception as e:
        logger.error(f"HyDE failed: {e}")
        return query


async def rerank_documents(query: str, documents: List[Dict[str, Any]], top_k: int = 5, min_score: float = 7.0) -> List[Dict[str, Any]]:
    if not documents:
        return []

    # Fetch dynamic config
    config = await get_llm_config()
    model_name = config["steps"]["rag_search"]["model"] # Reusing search model for reranking

    llm = get_llm(model_name=model_name, temperature=0.0)
    prompt = PromptTemplate.from_template(RERANK_PROMPT_TEMPLATE)
    chain = prompt | llm

    scored_docs = []
    dropped_count = 0

    # Reranking can be parallelized
    # For simplicity, sequential await loop or gather
    # Let's do sequential for now to avoid complexity with rate limits
    for doc in documents:
        try:
            content_preview = doc["content"][:1000]
            response = await chain.ainvoke({"query": query, "content": content_preview})
            text = response.content.replace("```json", "").replace("```", "").strip()
            score_data = json.loads(text)
            score = score_data.get("score", 0)

            if score >= min_score:
                doc["rerank_score"] = score
                scored_docs.append(doc)
            else:
                dropped_count += 1

        except Exception as e:
            logger.warning(f"Reranking failed for doc {doc.get('id')}: {e}")
            # Decide if we keep failed reranks. Safest is to drop or give low score.
            # Here we drop them to be safe against noise.
            dropped_count += 1

    scored_docs.sort(key=lambda x: x["rerank_score"], reverse=True)

    logger.info(f"⚖️ Reranker: Kept {len(scored_docs)} docs (Dropping {dropped_count} below score {min_score})")

    return scored_docs[:top_k]


from rag.chains.retrieval import get_query_expansion_chain
from rag.chains.rerank import rerank_documents_lcel

async def retrieve_context(
    client_id: int, query: str, external_context: Optional[str] = None
) -> str:
    # 1. Query Expansion (Multi-Query)
    expansion_chain = await get_query_expansion_chain()
    try:
        queries = await expansion_chain.ainvoke({"query": query})
        queries.append(query) # Ensure original is included
        queries = list(set(queries)) # Dedupe strings
        logger.info(f"✨ Expanded Queries ({len(queries)}): {queries}")
    except Exception as e:
        logger.warning(f"Query expansion failed: {e}")
        queries = [query]

    # 2. Embed & Search (Batch)
    embed_model = get_embeddings()
    all_docs_map = {} # handle duplicates by ID

    for q in queries:
        try:
            # We treat HyDE/Expansion as just text queries now.
            # Ideally we embed each expanded query.
            query_vector = await embed_model.aembed_query(q)

            # Fetch candidates for each query
            # We lower candidate_limit per query to avoid explosion, but keep high enough for recall
            candidates = await search_documents_hybrid(client_id, query_vector, q, limit=10)

            for doc in candidates:
                all_docs_map[doc["id"]] = doc
        except Exception as e:
            logger.warning(f"Search failed for query '{q}': {e}")

    unique_candidates = list(all_docs_map.values())
    logger.info(f"🔍 Found {len(unique_candidates)} unique candidates from {len(queries)} queries.")

    # 3. Rerank with Filtering (LCEL)
    # We enforce a strict threshold (7/10) to avoid polluting context with irrelevant "fluff"
    ranked_docs = await rerank_documents_lcel(query, unique_candidates, top_k=5, min_score=7.0)

    doc_context = "\n\n".join(
        [f"Source: {r['filename']}\n{r['content']}" for r in ranked_docs]
    )

    full_context = ""
    if external_context:
        full_context += f"External Context:\n{external_context}\n\n"
    if doc_context:
        full_context += f"Document Context:\n{doc_context}"

    if not full_context:
        full_context = "No relevant documents found."

    return full_context


def determine_intent(complexity_score: int, pricing_intent: bool) -> bool:
    # Returns True if RAG is required, False for Small Talk
    if complexity_score is not None and complexity_score < 2 and not pricing_intent:
        return False
    return True


async def _save_interaction_to_db(session: AsyncSession, session_id: UUID, query: str, answer: str, client_id: int):
    try:
        # We insert directly to ChatMessage logic
        # Ensure session exists
        existing_session = await session.get(ChatSession, session_id)
        if not existing_session:
            new_session = ChatSession(id=session_id, client_id=client_id)
            session.add(new_session)
            await session.flush() # Ensure ID is available

        # Insert messages
        user_msg = ChatMessage(session_id=session_id, role="user", content=query)
        ai_msg = ChatMessage(session_id=session_id, role="assistant", content=answer)

        session.add(user_msg)
        session.add(ai_msg)
        await session.commit()
    except Exception as e:
        logger.error(f"Failed to save history: {e}")


async def save_interaction(
    session_id: UUID,
    query: str,
    answer: str,
    client_id: int,
    db: Optional[AsyncSession] = None
):
    # We need to make sure session_id is UUID object
    if isinstance(session_id, str):
        session_id = UUID(session_id)

    if db:
        await _save_interaction_to_db(db, session_id, query, answer, client_id)
    else:
        async with async_session_maker() as session:
            await _save_interaction_to_db(session, session_id, query, answer, client_id)


async def prepare_conversation_context(
    session_id: Optional[UUID],
    query: str,
    include_history_in_prompt: bool
) -> Tuple[str, str]:
    """Prepares the conversation context:
    1. Fetches history.
    2. Contextualizes the query (rewrites it based on history).
    3. Formats history into a string for the LLM.
    """
    history = []
    if session_id:
        history = await get_chat_history(session_id)
        query = await contextualize_query(query, history)

    history_str = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in history])
    if not include_history_in_prompt:
        history_str = ""

    return query, history_str


async def generate_rag_response(
    client_id: int,
    query: str,
    history_str: str,
    external_context: Optional[str],
    llm: Any
) -> Tuple[str, str]:
    """Executes the RAG flow:
    1. Retrieves context (HyDE -> Embed -> Hybrid Search -> Rerank).
    2. Generates answer using RAG prompt.
    """
    context_str = await retrieve_context(client_id, query, external_context)
    prompt = PromptTemplate.from_template(RAG_ANSWER_PROMPT_TEMPLATE)
    chain = prompt | llm

    response = await chain.ainvoke({
        "lang_instruction": "Language: Same as the User's Latest Question (Detect it)", # Dynamic
        "history_str": history_str,
        "context_str": context_str,
        "search_query": query
    })
    return response.content, context_str

    return response.content, context_str


async def generate_small_talk_response(
    query: str,
    history_str: str,
    llm: Any
) -> str:
    """Generates a small talk response using the LLM."""
    prompt = PromptTemplate.from_template(SMALL_TALK_PROMPT_TEMPLATE)
    chain = prompt | llm
    response = await chain.ainvoke({
        "lang_instruction": "Language: Same as the User's Latest Question (Detect it)",
        "history_str": history_str,
        "search_query": query
    })
    return response.content


async def generate_answer(
    client_id: int,
    query: str,
    session_id: Optional[UUID] = None,
    complexity_score: int = 5,
    pricing_intent: bool = False,
    external_context: Optional[str] = None,
    save_history: bool = True,
    include_history_in_prompt: bool = True,
) -> Tuple[str, Optional[UUID], Optional[str]]:

    # 1. History & Contextualization
    query, history_str = await prepare_conversation_context(session_id, query, include_history_in_prompt)

    # 2. Intent
    requires_rag = determine_intent(complexity_score, pricing_intent)
    logger.info(f"🔍 RAG Decision: requires_rag={requires_rag} | complexity={complexity_score} | pricing_intent={pricing_intent}")

    # 3. Retrieval or Small Talk
    answer = ""
    context_str = ""

    # 4. Fetch Dynamic Config for Generation
    config = await get_llm_config()

    # 5. Logic for model selection based on complexity
    if complexity_score > 7:
        llm_model_name = config["steps"]["complex_reasoning"]["model"]
    else:
        llm_model_name = config["steps"]["generation"]["model"]

    logger.info(f"🤖 Model Selection: {llm_model_name} (Complexity: {complexity_score})")

    llm = get_llm(model_name=llm_model_name)

    if requires_rag:
        answer, context_str = await generate_rag_response(
            client_id, query, history_str, external_context, llm
        )
        logger.info(f"📚 RAG Context Length: {len(context_str)} chars | Answer Length: {len(answer)} chars")
    else:
        answer = await generate_small_talk_response(query, history_str, llm)
        logger.info(f"💬 Small Talk Answer Length: {len(answer)} chars")

    # 6. Save Interaction
    if session_id and save_history:
        await save_interaction(session_id, query, answer, client_id)
        logger.info(f"💾 Interaction Saved to DB (Session: {session_id})")

    return answer, session_id, context_str


async def delete_chat_session(session_id: UUID, db: AsyncSession):
    """Deletes a RAG chat session and its history."""
    stmt = select(ChatSession).where(ChatSession.id == session_id)
    result = await db.execute(stmt)
    session = result.scalars().first()
    if session:
        await db.delete(session)


async def get_rag_context(
    client_id: int,
    query: str,
    session_id: Optional[UUID] = None,
) -> str:
    """Retrieves the raw RAG context (documents) for a query, handling contextualization.
    Does NOT generate an answer (Pure Retrieval).
    """
    # 1. History & Contextualization
    # We always include history for contextualization
    query, _ = await prepare_conversation_context(session_id, query, include_history_in_prompt=True)

    # 2. Retrieve
    context_str = await retrieve_context(client_id, query)

    return context_str


