from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.runnables import RunnableConfig
from app.models import ChatSession, Tenant
from app.core.logger import Log
from app.rag.retrieve import get_chat_history
from langchain_core.messages import HumanMessage
from app.orchestration.state import ChatState

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

    # 2. Fetch History dynamically from Chatwoot APIs to populate RAG and Chitchat context
    client = config["configurable"].get("chatwoot_client")
    history = []
    if state.get("account_id") and client:
        history = await get_chat_history(client, state['session_id'], state['account_id'], limit=6)
        # Remove the latest message if it's the exact same as the user query (prevent duplication)
        if history and isinstance(history[-1], HumanMessage) and history[-1].content == state["user_message"]:
            history = history[:-1]

    return {"chat_history": history}
