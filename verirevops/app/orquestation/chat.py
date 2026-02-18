import os
from typing import List, Literal, TypedDict, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from datetime import datetime

from app.models import ChatSession, ChatMessage
from app.rag.retrieve import invoke_rag_graph, get_chat_history
from app.prompts import ROUTER_SYSTEM_PROMPT, CHITCHAT_SYSTEM_PROMPT

# --- Configuration ---
MODEL_NAME = os.getenv("MODEL", "gemini-2.0-flash")
# llm = ChatGoogleGenerativeAI(model=MODEL_NAME, temperature=0)
api_key = os.getenv("GOOGLE_API_KEY")

# --- State ---
class ChatState(TypedDict):
    tenant_id: int
    session_id: int
    user_message: str
    chat_history: List[BaseMessage]
    intent: str  # "rag", "chitchat", "handoff"
    ai_response: str
    summary_needed: bool

# --- Nodes ---

async def load_and_ensure_session(state: ChatState, db: AsyncSession) -> ChatState:
    """
    Ensures session exists and loads history.
    Example placeholder: In real app, `session_id` should effectively be `conversation_id` from Chatwoot map.
    """
    # 1. Check/Create Session logic
    stmt = select(ChatSession).where(ChatSession.id == state['session_id'])
    result = await db.execute(stmt)
    session = result.scalars().first()

    if not session:
        # Ensure Tenant exists
        from app.models import Tenant
        stmt_tenant = select(Tenant).where(Tenant.id == state['tenant_id'])
        result_tenant = await db.execute(stmt_tenant)
        tenant = result_tenant.scalars().first()

        if not tenant:
            # Create Tenant (Auto-provisioning for test/webhook)
            try:
                tenant = Tenant(
                    id=state['tenant_id'],
                    name=f"Tenant {state['tenant_id']}",
                    slug=f"tenant-{state['tenant_id']}",
                    url=f"https://example.com/tenant-{state['tenant_id']}"
                )
                db.add(tenant)
                await db.flush()
            except Exception as e:
                # Handle race condition or error
                await db.rollback()
                # Try fetching again
                result_tenant = await db.execute(stmt_tenant)
                tenant = result_tenant.scalars().first()

        if tenant:
            session = ChatSession(id=state['session_id'], tenant_id=state['tenant_id'])
            db.add(session)
            await db.commit()
        else:
             # Should probably log error properly in real app
             pass

    # 2. Persist User Message
    msg = ChatMessage(
        session_id=state['session_id'],
        role='user',
        content=state['user_message'],
        created_at=datetime.utcnow()
    )
    db.add(msg)
    await db.commit() # Commit to save user message and session/tenant if new

    # 3. Load History
    history = await get_chat_history(state['session_id'], db)
    return {"chat_history": history}

async def router_node(state: ChatState) -> ChatState:
    """
    Classifies the user's intent.
    """
    system_prompt = ROUTER_SYSTEM_PROMPT

    llm = ChatGoogleGenerativeAI(model=MODEL_NAME, temperature=0, google_api_key=api_key)

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=state['user_message'])]
    response = await llm.ainvoke(messages)
    intent = response.content.strip().lower()

    if intent not in ['rag', 'chitchat', 'handoff']:
        intent = 'chitchat' # Default fallback

    return {"intent": intent}

async def rag_node(state: ChatState, db: AsyncSession) -> ChatState:
    """
    Executes the RAG pipeline.
    """
    # invoke_rag_graph already handles history fetching, but we have it in state.
    # We pass the user query.
    # Note: invoke_rag_graph manages its own flow.
    answer = await invoke_rag_graph(state['session_id'], state['user_message'], db)
    return {"ai_response": answer, "summary_needed": True}

async def chitchat_node(state: ChatState) -> ChatState:
    """
    Simple LLM response for greetings/chitchat.
    """
    prompt = [
        SystemMessage(content=CHITCHAT_SYSTEM_PROMPT),
        *state['chat_history'], # Optional: Include history for context
        HumanMessage(content=state['user_message'])
    ]

    llm = ChatGoogleGenerativeAI(model=MODEL_NAME, temperature=0, google_api_key=api_key)

    response = await llm.ainvoke(prompt)
    return {"ai_response": response.content, "summary_needed": False}

async def persist_response_node(state: ChatState, db: AsyncSession) -> ChatState:
    """
    Saves the Assistant's response to the DB.
    """
    new_msg = ChatMessage(
        session_id=state['session_id'],
        role='assistant',
        content=state['ai_response'],
        created_at=datetime.utcnow()
    )
    db.add(new_msg)
    await db.commit()
    return {}

async def summarize_node(state: ChatState, db: AsyncSession) -> ChatState:
    """
    Async task to update session summary.
    In a real event-driven architecture, this might be a background task (FastAPI BackgroundTasks).
    For now, we execute it as part of the flow but it could be decoupled.
    """
    if not state.get("summary_needed"):
        return {}

    # Logic: Get full history -> Check if summary update is needed -> Update DB
    # For now, let's keep it simple and just return.
    # The actual summarization is expensive, so we might want to trigger it less often.
    return {}

# --- Graph Construction ---

def build_chat_graph(db: AsyncSession):
    """
    Builds the graph with the provided DB session injected into nodes.
    """
    workflow = StateGraph(ChatState)

    # Define Nodes with strict partials not needed if we use a wrapper,
    # but lambda/partial is easiest for 'db' injection.

    # We need to wrap async functions to be valid nodes
    async def ingest_step(state): return await load_and_ensure_session(state, db)
    async def rag_step(state): return await rag_node(state, db)
    async def persist_step(state): return await persist_response_node(state, db)
    async def summary_step(state): return await summarize_node(state, db)

    workflow.add_node("ingest", ingest_step)
    workflow.add_node("router", router_node)
    workflow.add_node("rag", rag_step)
    workflow.add_node("chitchat", chitchat_node)
    workflow.add_node("persist", persist_step)
    workflow.add_node("summarize", summary_step)

    # Edges
    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "router")

    # Conditional Logic
    def route_decision(state):
        return state['intent']

    workflow.add_conditional_edges(
        "router",
        route_decision,
        {
            "rag": "rag",
            "chitchat": "chitchat",
            "handoff": "chitchat" # Fallback to chitchat for now, or implement handoff
        }
    )

    workflow.add_edge("rag", "persist")
    workflow.add_edge("chitchat", "persist")
    workflow.add_edge("persist", "summarize")
    workflow.add_edge("summarize", END)

    return workflow.compile()

async def invoke_chat_orchestrator(tenant_id: int, session_id: int, message: str, db: AsyncSession):
    """
    Public entry point.
    """
    app = build_chat_graph(db)

    initial_state = ChatState(
        tenant_id=tenant_id,
        session_id=session_id,
        user_message=message,
        chat_history=[],
        intent="chitchat",
        ai_response="",
        summary_needed=False
    )

    # Execute
    final_state = await app.ainvoke(initial_state)
    return final_state['ai_response']
