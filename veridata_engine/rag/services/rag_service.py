import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from sqlalchemy import select

from bot.core.config import settings
from bot.core.db import async_session_maker
from bot.services.global_config_service import get_llm_config
from rag.models.sql import ChatMessage, ChatSession
from rag.storage.repository import search_documents_hybrid
from rag.utils.prompts import (
    CONTEXTUALIZE_PROMPT_TEMPLATE,
    HYDE_PROMPT_TEMPLATE,
    RAG_ANSWER_PROMPT_TEMPLATE,
    RERANK_PROMPT_TEMPLATE,
    SMALL_TALK_PROMPT_TEMPLATE,
)

logger = logging.getLogger(__name__)


def get_llm(model_name: str, temperature: float = 0.0):
    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY is not set.")
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=settings.google_api_key,
        temperature=temperature,
    )


def get_embeddings():
    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY is not set.")
    return GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=settings.google_api_key
    )


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


async def rerank_documents(query: str, documents: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
    if not documents:
        return []

    # Fetch dynamic config
    config = await get_llm_config()
    model_name = config["steps"]["rag_search"]["model"] # Reusing search model for reranking

    llm = get_llm(model_name=model_name, temperature=0.0)
    prompt = PromptTemplate.from_template(RERANK_PROMPT_TEMPLATE)
    chain = prompt | llm

    scored_docs = []
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
            doc["rerank_score"] = score
            scored_docs.append(doc)
        except Exception as e:
            logger.warning(f"Reranking failed for doc {doc.get('id')}: {e}")
            doc["rerank_score"] = 0
            scored_docs.append(doc)

    scored_docs.sort(key=lambda x: x["rerank_score"], reverse=True)
    return scored_docs[:top_k]


async def retrieve_context(
    client_id: int, query: str, external_context: Optional[str] = None
) -> str:
    # 1. HyDE
    hyde_query = await generate_hypothetical_answer(query)

    # 2. Embed
    embed_model = get_embeddings()
    # embed_query is usually sync in LangChain default wrapper but google-genai might be async?
    # Dictionary says embed_query is synchronous.
    # To make it async we might need run_in_executor or verify if GoogleGenerativeAIEmbeddings supports aembed_query
    # It usually does.
    query_vector = await embed_model.aembed_query(hyde_query)

    # 3. Hybrid Search
    candidate_limit = 20 # Fetch more for reranking
    candidates = await search_documents_hybrid(client_id, query_vector, query, candidate_limit)

    # 4. Rerank
    ranked_docs = await rerank_documents(query, candidates, top_k=5)

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


async def save_interaction(session_id: UUID, query: str, answer: str, client_id: int):
    # We need to make sure session_id is UUID object
    if isinstance(session_id, str):
        session_id = UUID(session_id)

    async with async_session_maker() as session:
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
    history = []
    if session_id:
        history = await get_chat_history(session_id)
        query = await contextualize_query(query, history)

    history_str = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in history])
    if not include_history_in_prompt:
        history_str = ""

    # 2. Intent
    requires_rag = determine_intent(complexity_score, pricing_intent)

    # 3. Retrieval or Small Talk
    answer = ""
    context_str = ""

    # Fetch Dynamic Config for Generation
    config = await get_llm_config()

    # Logic for model selection based on complexity
    if complexity_score > 7:
        llm_model_name = config["steps"]["complex_reasoning"]["model"]
    else:
        llm_model_name = config["steps"]["generation"]["model"]

    llm = get_llm(model_name=llm_model_name)

    if requires_rag:
        context_str = await retrieve_context(client_id, query, external_context)
        prompt = PromptTemplate.from_template(RAG_ANSWER_PROMPT_TEMPLATE)
        chain = prompt | llm

        response = await chain.ainvoke({
            "lang_instruction": "Language: Same as the User's Latest Question (Detect it)", # Dynamic
            "history_str": history_str,
            "context_str": context_str,
            "search_query": query
        })
        answer = response.content
    else:
        # For small talk, we might use generation model or a lighter one?
        # Let's use generation model for consistency (or could be mapped to 'small_talk' if config had it)
        # Using generation model as fallback
        prompt = PromptTemplate.from_template(SMALL_TALK_PROMPT_TEMPLATE)
        chain = prompt | llm
        response = await chain.ainvoke({
            "lang_instruction": "Language: Same as the User's Latest Question (Detect it)",
            "history_str": history_str,
            "search_query": query
        })
        answer = response.content

    # 4. Save Interaction
    # 4. Save Interaction
    if session_id and save_history:
        await save_interaction(session_id, query, answer, client_id)

    return answer, session_id, context_str
