import os
from typing import List, TypedDict, Optional
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from flashrank import Ranker, RerankRequest

from app.models import ChatSession, ChatMessage, RagChunk, RagFile

# --- Configuration ---
model_name = os.getenv("MODEL")
embedding_model = os.getenv("EMBEDDING_MODEL")
llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)
embeddings = GoogleGenerativeAIEmbeddings(model=embedding_model)
# FlashRank Reranker (Nano model is fast and runs locally)
reranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="/app/.cache/flashrank")

# --- State Definition ---
class RAGState(TypedDict):
    """
    Represents the state of our RAG pipeline.
    Passed between nodes in the graph.
    """
    session_id: int
    user_query: str                  # Original query from user
    chat_history: List[BaseMessage]  # Last 6 messages from DB

    contextualized_query: str        # Step 1: Query rewritten with history
    expanded_queries: List[str]      # Step 2: Variations of the query

    retrieved_docs: List[Document]   # Step 3: Raw results from Vector DB
    reranked_docs: List[Document]    # Step 4: Top K results after reranking

    final_answer: str                # Step 5: The LLM response


# --- Helper: Fetch History ---
async def get_chat_history(session_id: int, db: AsyncSession, limit: int = 6) -> List[BaseMessage]:
    """Fetch the last N messages for context."""
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    # Reverse to get chronological order (Oldest -> Newest)
    history = []
    for msg in reversed(rows):
        if msg.role == "user":
            history.append(HumanMessage(content=msg.content))
        else:
            history.append(AIMessage(content=msg.content))
    return history


# --- Node 1: Contextualize ---
async def contextualize_query(state: RAGState):
    """
    Step 1: Rewrite user query to be standalone based on chat history.
    """
    print(f"--- Node 1: Contextualize '{state['user_query']}' ---")

    if not state.get("chat_history"):
        # No history, so query is already standalone
        return {"contextualized_query": state["user_query"]}

    system_prompt = (
        "Given a chat history and the latest user question "
        "which might reference context in the chat history, "
        "formulate a standalone question which can be understood "
        "without the chat history. Do NOT answer the question, "
        "just reformulate it if needed and otherwise return it as is."
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{chat_history}"),
        ("human", "{question}"),
    ])

    chain = prompt | llm | StrOutputParser()
    new_query = await chain.ainvoke({
        "chat_history": state["chat_history"],
        "question": state["user_query"]
    })

    print(f"    -> Rewritten: '{new_query}'")
    return {"contextualized_query": new_query}


# --- Node 2: Expand (Multi-Query) ---
async def expand_query(state: RAGState):
    """
    Step 2: Generate 3 variations of the query to broaden search coverage.
    """
    query = state["contextualized_query"]
    print(f"--- Node 2: Expansion for '{query}' ---")

    system_prompt = (
        "You are a helpful assistant that generates multiple search queries based on a single input query. "
        "Generate 3 variations of the input query to overcome distance-based similarity limitations. "
        "Provide these alternative questions separated by newlines."
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{question}"),
    ])

    chain = prompt | llm | StrOutputParser()
    response = await chain.ainvoke({"question": query})

    # Parse result into list
    queries = [q.strip() for q in response.split("\n") if q.strip()]
    if query not in queries:
        queries.insert(0, query) # Ensure original is included

    print(f"    -> Expanded into {len(queries)} queries: {queries}")
    return {"expanded_queries": queries}


# --- Node 3: Retrieve ---
async def retrieve_documents(state: RAGState, db_session: AsyncSession):
    """
    Step 3: Search Vector DB for all expanded queries.
    """
    queries = state["expanded_queries"]
    print(f"--- Node 3: Retrieving for {len(queries)} queries ---")

    all_docs = []

    # We could do this in parallel, but keeping it simple/sequential loop for now
    for q in queries:
        # Generate embedding
        vector = await embeddings.aembed_query(q)

        # Search DB (using l2_distance)
        # We need to manually construct this since we are inside a node
        # but we need the db_session which isn't in State.
        # *Architecture Note*: usually we pass DB in config or bind it.
        # For simplicity, we will assume it is passed in 'configurable' or we cheat slightly
        # by passing it as an argument to the graph function wrapper.

        stmt = (
            select(RagChunk)
            .order_by(RagChunk.embedding.l2_distance(vector))
            .limit(5) # Fetch top 5 for EACH query variation
        )
        result = await db_session.execute(stmt)
        chunks = result.scalars().all()

        for chunk in chunks:
            all_docs.append(Document(
                page_content=chunk.content,
                metadata={"id": chunk.id, "chunk_index": chunk.chunk_index, **(chunk.chunk_metadata or {})}
            ))

    # Deduplicate by ID
    unique_docs = {doc.metadata["id"]: doc for doc in all_docs}
    unique_list = list(unique_docs.values())

    print(f"    -> Found {len(all_docs)} raw docs, {len(unique_list)} unique.")
    return {"retrieved_docs": unique_list}


# --- Node 4: Rerank ---
async def rerank_documents(state: RAGState):
    """
    Step 4: Rerank the retrieved documents using FlashRank.
    """
    docs = state["retrieved_docs"]
    query = state["contextualized_query"]
    print(f"--- Node 4: Reranking {len(docs)} docs ---")

    if not docs:
        return {"reranked_docs": []}

    # Format for FlashRank
    passages = [
        {"id": str(d.metadata["id"]), "text": d.page_content, "meta": d.metadata}
        for d in docs
    ]

    rerank_request = RerankRequest(query=query, passages=passages)
    results = reranker.rerank(rerank_request)

    # Validating results and taking top 5
    top_k = 5
    reranked_docs = []
    for res in results[:top_k]:
        reranked_docs.append(Document(
            page_content=res["text"],
            metadata=res["meta"]
        ))

    print(f"    -> Top {len(reranked_docs)} selected.")
    return {"reranked_docs": reranked_docs}


# --- Node 5: Generate ---
async def generate_answer(state: RAGState):
    """
    Step 5: Generate the final answer using context and history.
    """
    print("--- Node 5: Generating Answer ---")
    documents = state["reranked_docs"]
    context = "\n\n".join([doc.page_content for doc in documents])

    system_prompt = (
        "You are an assistant for question-answering tasks. "
        "Use the following pieces of retrieved context to answer the question. "
        "If you don't know the answer, just say that you don't know. "
        "Use three sentences maximum and keep the answer concise."
        "\n\nContext:\n{context}"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("placeholder", "{chat_history}"),
        ("human", "{question}"),
    ])

    chain = prompt | llm | StrOutputParser()

    response = await chain.ainvoke({
        "context": context,
        "chat_history": state["chat_history"],
        "question": state["contextualized_query"] # Use the cleaned query
    })

    return {"final_answer": response}


# --- Graph Construction ---

def build_rag_graph():
    workflow = StateGraph(RAGState)

    # Add Nodes
    workflow.add_node("contextualize", contextualize_query)
    workflow.add_node("expand", expand_query)
    # We need a wrapper for retrieve to handle the sync/async DB session injection pattern
    # For now, we will inject it at runtime invocation
    # workflow.add_node("retrieve", retrieve_documents)
    workflow.add_node("rerank", rerank_documents)
    workflow.add_node("generate", generate_answer)

    # Define Edges (Sequential)
    workflow.set_entry_point("contextualize")
    workflow.add_edge("contextualize", "expand")
    # Retrieve is special because it needs DB, so we handle it manually in the invoke function below
    # workflow.add_edge("expand", "retrieve")
    # workflow.add_edge("retrieve", "rerank")
    workflow.add_edge("rerank", "generate")
    workflow.add_edge("generate", END)

    return workflow.compile()

# --- Public Entry Point ---
async def invoke_rag_graph(session_id: int, user_query: str, db_session: AsyncSession):
    """
    Main function to run the RAG pipeline.
    """
    # 1. Fetch History
    history = await get_chat_history(session_id, db_session)

    # 2. Initialize State
    initial_state = RAGState(
        session_id=session_id,
        user_query=user_query,
        chat_history=history,
        contextualized_query="",
        expanded_queries=[],
        retrieved_docs=[],
        reranked_docs=[],
        final_answer=""
    )

    # 3. Manually orchestrate steps that need DB injection
    # (LangGraph doesn't easily support passing non-serializable args like DB sessions directly into nodes yet)

    # Step A: Run Graph PART 1 (Contextualize -> Expand)
    # We use a partial graph or just call nodes directly?
    # For user transparency ("i want to understand..."), let's run them explicitly step-by-step
    # instead of a black-box graph.execute().
    # This also solves the DB session injection nicely.

    print(f"\n=== Starting RAG Pipeline for Session {session_id} ===")

    # Step 1: Contextualize
    ctx_out = await contextualize_query(initial_state)
    initial_state.update(ctx_out)

    # Step 2: Expand
    exp_out = await expand_query(initial_state)
    initial_state.update(exp_out)

    # Step 3: Retrieve (Needs DB)
    ret_out = await retrieve_documents(initial_state, db_session)
    initial_state.update(ret_out)

    # Step 4: Rerank
    rank_out = await rerank_documents(initial_state)
    initial_state.update(rank_out)

    # Step 5: Generate
    gen_out = await generate_answer(initial_state)

    print("=== Pipeline Complete ===\n")
    return gen_out["final_answer"]
