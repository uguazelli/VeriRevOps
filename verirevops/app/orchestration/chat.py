from app.core.config import settings
from typing import List, TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from datetime import datetime
from langchain_core.runnables import RunnableConfig

from app.models import ChatSession, ChatMessage
from app.rag.retrieve import invoke_rag_graph, get_chat_history
from app.prompts import ROUTER_SYSTEM_PROMPT, CHITCHAT_SYSTEM_PROMPT
from app.core.logger import Log

# --- State ---
class ChatState(TypedDict):
    tenant_id: Annotated[int, "The ID of the tenant"]
    session_id: Annotated[int, "The ID of the chat session"]
    user_message: Annotated[str, "The message from the user"]
    chat_history: Annotated[List[BaseMessage], "The history of the chat"]
    intent: Annotated[str, "The classified intent: rag, chitchat, or handoff"]
    ai_response: Annotated[str, "The response from the AI"]
    summary_needed: Annotated[bool, "Whether a summary update is required"]

# --- Nodes ---

async def load_and_ensure_session(state: ChatState, config: RunnableConfig) -> dict:
    """
    Ensures the chat session exists and persists the incoming message.
    Populates 'chat_history' and ensures 'session_id' is valid in DB.
    """
    db: AsyncSession = config["configurable"].get("db")
    if not db:
        Log.error("DB session missing in Chat Orchestrator config")
        return {}
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

async def router_node(state: ChatState, config: RunnableConfig) -> dict:
    """
    Classifies the user message into 'rag', 'chitchat', or 'handoff'.
    Updates 'intent' based on 'user_message' and 'chat_history'.
    """
    system_prompt = ROUTER_SYSTEM_PROMPT

    llm = ChatGoogleGenerativeAI(model=settings.MODEL, temperature=settings.TEMPERATURE, google_api_key=settings.GOOGLE_API_KEY)

    # Include some history for better context (last 3 messages)
    history_context = state.get('chat_history', [])[-3:]

    messages = [
        SystemMessage(content=system_prompt),
        *history_context,
        HumanMessage(content=state['user_message'])
    ]

    response = await llm.ainvoke(messages, config=config)
    raw_intent = response.content.strip().lower()

    # Robust extraction: find any valid intent in the response
    intent = "chitchat" # Default
    if "rag" in raw_intent:
        intent = "rag"
    elif "handoff" in raw_intent:
        intent = "handoff"
    elif "chitchat" in raw_intent:
        intent = "chitchat"

    Log.orchestrator(f"Decision: '{intent}' (Raw: '{raw_intent}')")
    return {"intent": intent}

async def rag_node(state: ChatState, config: RunnableConfig) -> dict:
    """
    Triggers the RAG pipeline to generate a grounded answer.
    Populates 'ai_response' using retrieved knowledge filtered by 'tenant_id'.
    """
    db: AsyncSession = config["configurable"].get("db")
    answer = await invoke_rag_graph(state['session_id'], state['user_message'], db, state['tenant_id'])
    return {"ai_response": answer, "summary_needed": True}

async def chitchat_node(state: ChatState, config: RunnableConfig) -> dict:
    """
    Generates a conversational response for greetings or general talk.
    Populates 'ai_response' without using the RAG search pipeline.
    """
    prompt = [
        SystemMessage(content=CHITCHAT_SYSTEM_PROMPT),
        *state['chat_history'], # Optional: Include history for context
        HumanMessage(content=state['user_message'])
    ]

    llm = ChatGoogleGenerativeAI(model=settings.MODEL, temperature=settings.TEMPERATURE, google_api_key=settings.GOOGLE_API_KEY)

    response = await llm.ainvoke(prompt, config=config)
    return {"ai_response": response.content, "summary_needed": False}

async def persist_response_node(state: ChatState, config: RunnableConfig) -> dict:
    """
    Saves the final AI-generated response back to the chat history database.
    Appends an 'assistant' role message linked to 'session_id'.
    """
    db: AsyncSession = config["configurable"].get("db")
    new_msg = ChatMessage(
        session_id=state['session_id'],
        role='assistant',
        content=state['ai_response'],
        created_at=datetime.utcnow()
    )
    db.add(new_msg)
    await db.commit()
    return {}

async def summarize_node(state: ChatState, config: RunnableConfig) -> dict:
    """
    Updates the high-level conversation summary if necessary.
    Triggered when 'summary_needed' is true to condense chat context.
    """
    if not state.get("summary_needed"):
        return {}

    # Logic: Get full history -> Check if summary update is needed -> Update DB
    # For now, let's keep it simple and just return.
    # The actual summarization is expensive, so we might want to trigger it less often.
    return {}

# --- Graph Construction ---

def build_chat_graph():
    """
    Builds the graph. DB is injected via RunnableConfig at runtime.
    """
    workflow = StateGraph(ChatState)

    workflow.add_node("ingest", load_and_ensure_session)
    workflow.add_node("router", router_node)
    workflow.add_node("rag", rag_node)
    workflow.add_node("chitchat", chitchat_node)
    workflow.add_node("persist", persist_response_node)
    workflow.add_node("summarize", summarize_node)

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
            "handoff": "chitchat" # Fallback to chitchat for now
        }
    )

    workflow.add_edge("rag", "persist")
    workflow.add_edge("chitchat", "persist")
    workflow.add_edge("persist", "summarize")
    workflow.add_edge("summarize", END)

    return workflow.compile()

# Singleton Graph Instance
chat_graph = build_chat_graph()

async def invoke_chat_orchestrator(tenant_id: int, session_id: int, message: str, db: AsyncSession):
    """
    Public entry point using native LangGraph ainvoke.
    """

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
    config = {"configurable": {"db": db}}
    final_state = await chat_graph.ainvoke(initial_state, config=config)
    Log.success(f"Orchestration complete for Session {session_id}")
    return final_state['ai_response']
