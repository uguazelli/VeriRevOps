from typing import List, Optional
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.runnables import RunnableConfig

from app.orchestration.state import ChatState
from app.orchestration.nodes import (
    transcribe_node,
    load_and_ensure_session,
    router_node,
    rag_node,
    chitchat_node,
    handoff_node,
    persist_response_node,
    summarize_node,
)
from app.core.logger import Log
from app.core.chatwoot import ChatwootClient
from app.schemas.chat import OrchestrationInput

# --- Graph Construction ---

def build_chat_graph():
    """
    Constructs the state graph for the chat orchestrator.
    Flow: Transcribe -> Ingest -> Router -> (RAG | Chitchat | Handoff) -> Persist -> Summarize
    """
    workflow = StateGraph(ChatState)

    # Nodes
    workflow.add_node("transcribe", transcribe_node)
    workflow.add_node("ingest", load_and_ensure_session)
    workflow.add_node("router", router_node)
    workflow.add_node("rag", rag_node)
    workflow.add_node("chitchat", chitchat_node)
    workflow.add_node("handoff", handoff_node)
    workflow.add_node("persist", persist_response_node)
    workflow.add_node("summarize", summarize_node)

    # Edges
    workflow.set_entry_point("transcribe")
    workflow.add_edge("transcribe", "ingest")
    workflow.add_edge("ingest", "router")

    workflow.add_conditional_edges(
        "router",
        lambda x: x["intent"],
        {
            "rag": "rag",
            "chitchat": "chitchat",
            "handoff": "handoff"
        }
    )

    workflow.add_edge("rag", "persist")
    workflow.add_edge("chitchat", "persist")
    workflow.add_edge("handoff", "persist")
    workflow.add_edge("persist", "summarize")
    workflow.add_edge("summarize", END)

    return workflow.compile()

# Singleton Graph Instance
chat_graph = build_chat_graph()

async def invoke_chat_orchestrator(input_data: OrchestrationInput, db: AsyncSession, chatwoot_client: ChatwootClient):
    """
    Public entry point using native LangGraph ainvoke.
    """
    initial_state = ChatState(
        tenant_id=input_data.session_key.tenant_id,
        account_id=input_data.session_key.account_id,
        session_id=input_data.session_key.conversation_id,
        user_message=input_data.user_message,
        chat_history=[],
        intent="chitchat",
        ai_response="",
        summary_needed=False,
        attachments=input_data.attachments or []
    )

    # Execute
    config = {"configurable": {"db": db, "chatwoot_client": chatwoot_client}}
    final_state = await chat_graph.ainvoke(initial_state, config=config)
    Log.success(f"Orchestration complete for Session {input_data.session_key.conversation_id}")
    return final_state['ai_response'], final_state['intent']
