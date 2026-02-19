from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from app.core.config import settings
from app.prompts import CHITCHAT_SYSTEM_PROMPT
from app.orchestration.state import ChatState

async def chitchat_node(state: ChatState, config: RunnableConfig) -> dict:
    """
    Generates a conversational response for greetings or general talk.
    Populates 'ai_response' without using the RAG search pipeline.
    """
    prompt = [
        SystemMessage(content=CHITCHAT_SYSTEM_PROMPT),
        *state['chat_history'], # Optional: Include history for context
        HumanMessage(content=state['user_message'] or "Olá! Como posso ajudar hoje?")
    ]

    llm = ChatGoogleGenerativeAI(model=settings.MODEL, temperature=settings.TEMPERATURE, google_api_key=settings.GOOGLE_API_KEY)

    response = await llm.ainvoke(prompt, config=config)
    return {"ai_response": response.content, "summary_needed": False}
