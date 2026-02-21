from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from app.core.config import settings
from app.core.logger import Log
from app.prompts import ROUTER_SYSTEM_PROMPT
from app.orchestration.state import ChatState

async def router_node(state: ChatState, config: RunnableConfig) -> dict:
    """
    Classifies the user message into 'rag', 'chitchat', or 'handoff'.
    Updates 'intent' based on 'user_message' and 'chat_history'.
    """
    system_prompt = ROUTER_SYSTEM_PROMPT
    if state.get("custom_prompt"):
        system_prompt += f"\n\nAdditional Routing Instructions:\n{state['custom_prompt']}"

    llm = ChatGoogleGenerativeAI(model=settings.MODEL, temperature=settings.TEMPERATURE, google_api_key=settings.GOOGLE_API_KEY)

    # Include some history for better context (last 3 messages)
    history_context = state.get('chat_history', [])[-3:]

    messages = [
        SystemMessage(content=system_prompt),
        *history_context,
        HumanMessage(content=state['user_message'] or "Analyze the conversation context and determine the next step.")
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
