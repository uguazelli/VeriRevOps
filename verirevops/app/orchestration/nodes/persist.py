from langchain_core.runnables import RunnableConfig
from app.orchestration.state import ChatState
from app.core.logger import Log

async def persist_response_node(state: ChatState, config: RunnableConfig) -> dict:
    """
    Saves the final AI-generated response back to the chat history.
    Since Chatwoot is the source of truth, we rely on the ChatbotService
    to send the message back to Chatwoot, which handles persistence.
    """
    Log.info(f"AI response generated for session {state['session_id']}")
    return {}
