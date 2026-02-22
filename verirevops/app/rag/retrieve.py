from app.core.config import settings
from typing import List, TypedDict, Annotated, Optional
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from flashrank import Ranker, RerankRequest
from langchain_core.runnables import RunnableConfig
from app.core.logger import Log
from app.core.decorators import with_retries, log_and_ignore
from app.models import RagChunk, RagFile
from app.core.chatwoot import ChatwootClient
from app.prompts import (
    CONTEXTUALIZE_QUERY_SYSTEM_PROMPT,
    EXPAND_QUERY_SYSTEM_PROMPT,
    GENERATE_ANSWER_SYSTEM_PROMPT,
    RAG_USER_PROMPT,
)


try:
    reranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="/tmp/flashrank")
except Exception as e:
    Log.warning(f"Failed to initialize Ranker: {e}")
    reranker = None



# --- State Definition ---
class RAGState(TypedDict):
    """
    Represents the state of our RAG pipeline.
    Passed between nodes in the graph.
    """
    session_id: Annotated[int, "The ID of the chat session"]
    tenant_id: Annotated[int, "The ID of the tenant"]
    user_query: Annotated[str, "Original query from user"]
    account_id: Annotated[int, "The Chatwoot account ID"]
    chat_history: Annotated[List[BaseMessage], "Last messages from DB"]
    contextualized_query: Annotated[str, "Step 1: Query rewritten with history"]
    expanded_queries: Annotated[List[str], "Step 2: Variations of the query"]
    retrieved_docs: Annotated[List[Document], "Step 3: Raw results from Vector DB"]
    reranked_docs: Annotated[List[Document], "Step 4: Top K results after reranking"]
    custom_prompt: Annotated[Optional[str], "Custom instructions for the tenant"]
    languages: Annotated[Optional[str], "Comma-separated list of preferred languages"]
    final_answer: Annotated[str, "Step 5: The LLM response"]


# --- Helper: Fetch History ---
async def get_chat_history(client: ChatwootClient, session_id: int, account_id: int, limit: int = 10) -> List[BaseMessage]:
    """Fetch the last N messages for context from Chatwoot using an injected client."""
    messages = await client.get_messages(account_id, session_id, limit=limit)

    # Map roles to LangChain message types. By default Chatwoot uses "incoming" for user and "outgoing" for agent
    langchain_messages = []
    for msg in messages:
        content = msg.get("content")
        mtype = msg.get("message_type")
        if not content:
            continue

        mtype_str = "user" if mtype == 0 or str(mtype).lower() == "incoming" else "assistant"
        role_map = {"user": HumanMessage, "assistant": AIMessage}

        langchain_messages.append(
            role_map.get(mtype_str, HumanMessage)(content=content)
        )

    return langchain_messages


# --- Node 1: Contextualize ---
async def contextualize_query(state: RAGState, config: RunnableConfig) -> dict:
    """
    Rewrites the user's query into a standalone version based on chat history.
    Transforms 'user_query' using 'chat_history' into 'contextualized_query'.
    """
    Log.rag(f"Contextualizing '{state['user_query']}'", step="Node 1")

    if not state.get("chat_history"):
        # No history, so query is already standalone
        return {"contextualized_query": state["user_query"]}

    system_prompt = CONTEXTUALIZE_QUERY_SYSTEM_PROMPT

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{chat_history}"),
        ("human", "{question}"),
    ])

    llm = ChatGoogleGenerativeAI(model=settings.MODEL, temperature=settings.TEMPERATURE, google_api_key=settings.GOOGLE_API_KEY)
    chain = prompt | llm | StrOutputParser()
    new_query = await chain.ainvoke({
        "chat_history": state["chat_history"],
        "question": state["user_query"]
    }, config=config)

    return {"contextualized_query": new_query}


# --- Node 2: Expand (Multi-Query) ---
async def expand_query(state: RAGState, config: RunnableConfig) -> dict:
    """
    Generates multiple search query variations to optimize coverage.
    Transforms 'contextualized_query' into a list of 'expanded_queries'.
    """
    query = state["contextualized_query"]
    Log.rag(f"Expanding queries for '{query}'", step="Node 2")

    system_prompt = EXPAND_QUERY_SYSTEM_PROMPT

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{question}"),
    ])

    llm = ChatGoogleGenerativeAI(model=settings.MODEL, temperature=settings.TEMPERATURE, google_api_key=settings.GOOGLE_API_KEY)
    chain = prompt | llm | StrOutputParser()
    response = await chain.ainvoke({"question": query}, config=config)

    # Parse result into list
    queries = [q.strip() for q in response.split("\n") if q.strip()]
    if query not in queries:
        queries.insert(0, query) # Ensure original is included

    return {"expanded_queries": queries}


# --- Node 3: Retrieve ---
async def retrieve_documents(state: RAGState, config: RunnableConfig) -> dict:
    """
    Searches the Vector DB for chunks relevant to all expanded queries.
    Populates 'retrieved_docs' with matches filtered by 'tenant_id'.
    """
    db_session: AsyncSession = config["configurable"].get("db")
    if not db_session:
        Log.error("Database session missing in RAG Graph config")
        return {"retrieved_docs": []}

    # Sanitize queries to avoid potential 500 errors from invisible chars
    raw_queries = state["expanded_queries"]
    queries = []
    for q in raw_queries:
        # Force string, strip whitespace
        s = str(q).strip()
        # Remove non-printable characters just in case
        s = "".join(c for c in s if c.isprintable())
        if s:
            queries.append(s)

    Log.rag(f"Retrieving for {len(queries)} queries", step="Node 3")

    # Instantiate embeddings locally
    embeddings = GoogleGenerativeAIEmbeddings(model=settings.EMBEDDING_MODEL, google_api_key=settings.GOOGLE_API_KEY)

    all_docs = []
    for q in queries:
        # 1. Get embedding with retry
        vector = await _get_embedding_with_retry(embeddings, q)
        if not vector:
            continue

        # 2. Fetch chunks from DB
        chunks = await _fetch_top_chunks(db_session, vector, state["tenant_id"])

        # 3. Convert to Document objects
        for chunk in chunks:
            all_docs.append(Document(
                page_content=chunk.content,
                metadata={"id": chunk.id, "chunk_index": chunk.chunk_index, **(chunk.chunk_metadata or {})}
            ))

    # Deduplicate by ID
    unique_docs = {doc.metadata["id"]: doc for doc in all_docs}
    unique_list = list(unique_docs.values())

    Log.rag(f"Found {len(all_docs)} raw docs, {len(unique_list)} unique.")
    return {"retrieved_docs": unique_list}


@with_retries(attempts=3, delay=1.0, log_message="Embedding failed")
async def _get_embedding_with_retry(embeddings: GoogleGenerativeAIEmbeddings, query: str) -> Optional[List[float]]:
    """Helper to fetch embeddings with exponential backoff."""
    return await embeddings.aembed_query(query)



async def _fetch_top_chunks(db: AsyncSession, vector: List[float], tenant_id: int, limit: int = 5) -> List[RagChunk]:
    """Helper to fetch top relevant chunks for a tenant."""
    stmt = (
        select(RagChunk)
        .join(RagFile, RagChunk.file_id == RagFile.id)
        .where(RagFile.tenant_id == tenant_id)
        .order_by(RagChunk.embedding.l2_distance(vector))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


# --- Node 4: Rerank ---
@log_and_ignore(default_return={"reranked_docs": []}, log_level="error")
async def rerank_documents(state: RAGState, config: RunnableConfig) -> dict:
    """
    Reranks retrieved documents using FlashRank for higher precision.
    Transforms 'retrieved_docs' into a prioritized 'reranked_docs' list.
    """
    docs = state["retrieved_docs"]
    query = state["contextualized_query"]
    Log.rag(f"Reranking {len(docs)} documents", step="Node 4")

    if not docs:
        return {"reranked_docs": []}

    # Format for FlashRank
    passages = [
        {"id": str(d.metadata["id"]), "text": d.page_content, "meta": d.metadata}
        for d in docs
    ]

    reranked_docs = []
    if reranker:
        rerank_request = RerankRequest(query=query, passages=passages)
        results = reranker.rerank(rerank_request)

        # Validating results and taking top 5
        top_k = 5
        for res in results[:top_k]:
            reranked_docs.append(Document(
                page_content=res["text"],
                metadata=res["meta"]
            ))
    else:
        reranked_docs = docs[:5] # Fallback if reranker not init

    return {"reranked_docs": reranked_docs}


# --- Node 5: Generate ---
async def generate_answer(state: RAGState, config: RunnableConfig) -> dict:
    """
    Synthesizes the final answer using the reranked documents and history.
    Populates 'final_answer' using 'reranked_docs' and 'chat_history'.
    """
    Log.rag(f"Generating overall answer", step="Node 5")
    documents = state["reranked_docs"]
    context = "\n\n".join([doc.page_content for doc in documents])

    system_prompt = GENERATE_ANSWER_SYSTEM_PROMPT
    if state.get("custom_prompt"):
        system_prompt += f"\n\nAdditional Instructions:\n{state['custom_prompt']}"

    if state.get("languages"):
        system_prompt += f"\n\nLanguage Consistency:\nAlways respond in the user's language. If it is not clear or you are in doubt, you MUST respond in one of these languages: {state['languages']}."

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{chat_history}"),
        ("human", RAG_USER_PROMPT),
    ])

    llm = ChatGoogleGenerativeAI(model=settings.MODEL, temperature=settings.TEMPERATURE, google_api_key=settings.GOOGLE_API_KEY)
    chain = prompt | llm | StrOutputParser()

    response = await chain.ainvoke({
        "context": context,
        "chat_history": state["chat_history"],
        "question": state["contextualized_query"] # Use the cleaned query
    }, config=config)

    return {"final_answer": response}


# --- Graph Construction ---

def build_rag_graph():
    workflow = StateGraph(RAGState)

    # Add Nodes
    workflow.add_node("contextualize", contextualize_query)
    workflow.add_node("expand", expand_query)
    workflow.add_node("retrieve", retrieve_documents)
    workflow.add_node("rerank", rerank_documents)
    workflow.add_node("generate", generate_answer)

    # Define Edges (Sequential)
    workflow.set_entry_point("contextualize")
    workflow.add_edge("contextualize", "expand")
    workflow.add_edge("expand", "retrieve")
    workflow.add_edge("retrieve", "rerank")
    workflow.add_edge("rerank", "generate")
    workflow.add_edge("generate", END)

    return workflow.compile()

# Singleton Graph Instance
rag_graph = build_rag_graph()

# --- Public Entry Point ---
async def invoke_rag_graph(session_id: int, user_query: str, db_session: AsyncSession, tenant_id: int, account_id: int, chat_history: List[BaseMessage] = None, custom_prompt: str = None, languages: str = None):
    """
    Main function to run the RAG pipeline using native LangGraph.
    """
    Log.divider(f"RAG SESSION {session_id}")

    # 1. Initialize State
    initial_state = RAGState(
        session_id=session_id,
        tenant_id=tenant_id,
        account_id=account_id,
        user_query=user_query,
        chat_history=chat_history or [],
        contextualized_query="",
        expanded_queries=[],
        retrieved_docs=[],
        reranked_docs=[],
        custom_prompt=custom_prompt,
        languages=languages,
        final_answer=""
    )

    # 2. Native Invocation with DB in config
    config = {"configurable": {"db": db_session}}
    final_state = await rag_graph.ainvoke(initial_state, config=config)

    Log.success(f"RAG Pipeline complete")
    return final_state["final_answer"]
