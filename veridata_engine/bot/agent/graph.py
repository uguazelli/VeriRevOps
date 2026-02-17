from langgraph.prebuilt import create_react_agent

from bot.agent.tools import lookup_pricing, search_knowledge_base, transfer_to_human
from bot.core.config import settings
from bot.core.ai import get_llm

# Simple cache to avoid rebuilding graph if model is same
_agent_cache = {}

def get_agent_app(model_name: str):

    if model_name in _agent_cache:
        return _agent_cache[model_name]

    llm = get_llm(model_name=model_name, temperature=0)

    tools = [search_knowledge_base, lookup_pricing, transfer_to_human]

    # We use LangGraph's prebuilt create_react_agent
    agent = create_react_agent(llm, tools)

    _agent_cache[model_name] = agent
    return agent
