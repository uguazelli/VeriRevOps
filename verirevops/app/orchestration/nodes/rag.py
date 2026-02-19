from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.runnables import RunnableConfig
from app.rag.retrieve import invoke_rag_graph
from app.orchestration.state import ChatState

async def rag_node(state: ChatState, config: RunnableConfig) -> dict:
    """
    Triggers the RAG pipeline to generate a grounded answer.
    Populates 'ai_response' using retrieved knowledge filtered by 'tenant_id'.
    """
    db: AsyncSession = config["configurable"].get("db")
    answer = await invoke_rag_graph(state['session_id'], state['user_message'], db, state['tenant_id'])
    return {"ai_response": answer, "summary_needed": True}
