from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from rag.services.rag_service import generate_answer
from bot.integrations.sheets import fetch_google_sheet_data
import logging
import uuid

logger = logging.getLogger(__name__)

@tool
async def search_knowledge_base(query: str, config: RunnableConfig) -> str:
    """
    Search the company's knowledge base for policies, services, contact info, and general questions.
    Use this for anything NOT related to specific product pricing if you have the product name.
    Args:
        query: The search question or keywords.
    """
    # 1. Extract Config from Runtime
    # The 'configurable' dict is passed via ainvoke(..., config={"configurable": {...}})
    configuration = config.get("configurable", {})
    rag_config = configuration.get("rag_config", {})

    if not rag_config:
        return "Error: RAG Configuration missing. Cannot search."

    # 2. Setup Client
    # 2. Setup Client
    try:
        # We ignore base_url and api_key from config as we use internal service
        # For now, we hardcode client_id=1 as per migration, or we could look it up.
        client_id = 1

        # Session ID handling
        rag_session_id_str = configuration.get("rag_session_id")
        rag_session_id = None
        if rag_session_id_str:
            try:
                rag_session_id = uuid.UUID(rag_session_id_str)
            except:
                pass

        # 3. Call RAG Internal Service
        # We pass session_id so 'contextualize_query' can resolve pronouns (e.g. "how much is it?").
        # We pass save_history=False because the Agent manages the persistence.
        answer, new_session_id, _ = await generate_answer(
            client_id=client_id,
            query=query,
            session_id=rag_session_id,
            complexity_score=5,
            pricing_intent=False,
            save_history=False,
            include_history_in_prompt=False
        )

        return answer

    except Exception as e:
        logger.error(f"RAG Tool Error: {e}")
        return "I'm having trouble retrieving information from the knowledge base."


@tool
async def lookup_pricing(query: str, config: RunnableConfig) -> str:
    """
    Fetch the product price list.
    Args:
        query: What the user is looking for.
               - If looking for a specific item, pass the name (e.g. "shampoo", "haircut").
               - If the user asks for the "menu", "price list", "services", "everything", or anything else that can indicate the user wants to see the entire prices's catalog, pass the exact string "ALL".
    """
    configuration = config.get("configurable", {})
    google_sheets_url = configuration.get("google_sheets_url")
    # Check if client is configured as Enterprise (large catalog)
    client_config = configuration.get("client_config", {})
    is_enterprise = client_config.get("is_enterprise", False)

    if not google_sheets_url:
        return "Error: No pricing sheet configured."

    # Handle "ALL" intent from Agent
    if query.strip().upper() == "ALL":
        query = None # This triggers "show all" in sheets logic

    # Enterprise Logic: Force specific search (unless query is None/ALL)
    if is_enterprise and query:
        # We rely on the search function/tool to filter results.
        # This allows multi-language support without hardcoded lists.
        clean_query = query.lower().strip()

        # Perform filtered search
        try:
            data = await fetch_google_sheet_data(google_sheets_url, query=clean_query)
            if not data:
                 return "No matching products found."
            return f"SEARCH RESULTS for '{query}':\n{data}"
        except Exception as e:
            logger.error(f"Pricing Tool Error: {e}")
            return "Could not fetch pricing data."

    # Standard Logic (Small Catalog or "ALL" request): Dump everything
    try:
        # We pass the query just in case, but usually we dump all for small clients
        # unless they asked for something specific.
        # Actually, for small clients, let's just dump ALL so the AI has full context
        # (cross-selling, alternatives).
        data = await fetch_google_sheet_data(google_sheets_url, query=None)
        if not data:
            return "The pricing sheet is empty."
        return f"PRICING DATA:\n{data}"
    except Exception as e:
        logger.error(f"Pricing Tool Error: {e}")
        return "Could not fetch pricing data."


@tool
def transfer_to_human() -> str:
    """
    Call this tool when the user explicitly asks to speak with a human or support agent,
    OR when you cannot resolve the user's issue after trying.
    IMPORTANT: Before calling this, check if you have the user's Name and Contact Info (Email/Phone).
    If missing, ASK them for it first (e.g. "To ensure we can reach you...").
    Only call this tool AFTER they provide it or if they refuse.
    """
    return "TRANSFERRED_TO_HUMAN"
