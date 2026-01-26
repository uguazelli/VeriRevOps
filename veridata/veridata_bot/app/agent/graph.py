from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from app.agent.tools import lookup_pricing, search_knowledge_base, transfer_to_human
from app.core.config import settings

# Simple cache to avoid rebuilding graph if model is same
_agent_cache = {}

def get_agent_app(model_name: str):

    if model_name in _agent_cache:
        return _agent_cache[model_name]

    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=0,
        google_api_key=settings.google_api_key,
    )

    tools = [search_knowledge_base, lookup_pricing, transfer_to_human]

    # We use LangGraph's prebuilt create_react_agent
    agent = create_react_agent(llm, tools)

    _agent_cache[model_name] = agent
    return agent
