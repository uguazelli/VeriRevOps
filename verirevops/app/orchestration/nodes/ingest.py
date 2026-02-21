from langchain_core.runnables import RunnableConfig
from app.services.tenant.service import TenantService
from app.services.chat_session.service import ChatSessionService
from app.schemas.chat import SessionKey
from app.core.logger import Log
from app.rag.retrieve import get_chat_history
from langchain_core.messages import HumanMessage
from app.orchestration.state import ChatState

async def load_and_ensure_session(state: ChatState, config: RunnableConfig) -> dict:
    """
    Ensures the chat session exists and persists the incoming message.
    Populates 'chat_history' and ensures 'session_id' is valid in DB.
    """
    db = config["configurable"].get("db")
    client = config["configurable"].get("chatwoot_client")

    if not db:
        Log.error("DB session missing in Chat Orchestrator config")
        return {}

    # 1. Construct Key
    session_key = SessionKey(
        tenant_id=state['tenant_id'],
        account_id=state['account_id'],
        conversation_id=state['session_id']
    )

    # 2. Ensure Tenant (Auto-provisioning)
    tenant_service = TenantService(db)
    tenant = await tenant_service.get_or_create_tenant(session_key.tenant_id)
    custom_prompt = tenant.custom_prompt if tenant else None

    # 3. Ensure Session
    session_service = ChatSessionService(db)
    await session_service.ensure_session(session_key)

    # 4. Fetch History
    history = []
    if client:
        history = await get_chat_history(client, session_key.conversation_id, session_key.account_id, limit=10)
        # Prevent duplication of current message
        if history and isinstance(history[-1], HumanMessage) and history[-1].content == state["user_message"]:
            history = history[:-1]

    return {"chat_history": history, "custom_prompt": custom_prompt}
