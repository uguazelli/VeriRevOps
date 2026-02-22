from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from app.core.config import settings
from app.prompts import HANDOFF_SYSTEM_PROMPT
from app.orchestration.state import ChatState

async def handoff_node(state: ChatState, config: RunnableConfig) -> dict:
    """
    Formulates a brief message confirming the transfer to a human agent.
    Populates 'ai_response' using the handoff-specific instructions.
    """
    prompt = [
        SystemMessage(content=HANDOFF_SYSTEM_PROMPT),
        HumanMessage(content=state['user_message'] or "Por favor, transfira esta conversa para um atendente humano.")
    ]

    llm = ChatGoogleGenerativeAI(model=settings.MODEL, temperature=settings.TEMPERATURE, google_api_key=settings.GOOGLE_API_KEY)
    response = await llm.ainvoke(prompt, config=config)
    return {"ai_response": response.content, "summary_needed": False}
