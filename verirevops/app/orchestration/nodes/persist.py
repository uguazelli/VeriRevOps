from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.runnables import RunnableConfig
from app.models import ChatMessage
from app.orchestration.state import ChatState

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
