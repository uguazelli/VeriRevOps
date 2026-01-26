import logging
import uuid
from typing import Dict, Any, Tuple

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langfuse.langchain import CallbackHandler

from app.agent.graph import get_agent_app
from app.agent.prompts import AGENT_SYSTEM_PROMPT
from app.core.llm_config import get_llm_config
from app.integrations.rag import RagClient
from app.models.session import BotSession

logger = logging.getLogger(__name__)

async def run_agent_pipeline(
    db: AsyncSession,
    session: BotSession,
    user_query: str,
    configs: Dict[str, Any],
    event_data: Any # ChatwootEvent
) -> Tuple[str, bool]:
    """
    Executes the full Agent pipeline:
    1. Fetches history (RAG).
    2. Builds Context (System Prompt + Custom Instructions).
    3. Runs LangGraph Agent.
    4. Persists interaction to RAG history.

    Returns:
        (answer: str, requires_human: bool)
    """
    rag_config = configs.get("rag", {})
    client_config = configs.get("client_config", {})

    # --- 1. Fetch History ---
    history_messages = []
    if session.rag_session_id:
        try:
            rag_client = RagClient(
                base_url=rag_config["base_url"],
                api_key=rag_config.get("api_key", ""),
                tenant_id=rag_config["tenant_id"],
            )
            history_data = await rag_client.get_history(session.rag_session_id)
            for msg in history_data:
                if msg["role"] == "user":
                    history_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "ai":
                    history_messages.append(AIMessage(content=msg["content"]))
        except Exception as e:
            logger.warning(f"Failed to fetch chat history: {e}")

    # --- 2. Build Prompt ---
    custom_instructions = client_config.get("custom_instructions", "")
    final_system_prompt = AGENT_SYSTEM_PROMPT
    if custom_instructions:
        final_system_prompt += f"\n\n**CUSTOM CLIENT INSTRUCTIONS (OVERRIDE DEFAULT):**\n{custom_instructions}"

    full_messages = [SystemMessage(content=final_system_prompt)] + history_messages + [HumanMessage(content=user_query)]

    # --- 3. Run Agent ---
    initial_state = {"messages": full_messages}

    # Runtime Config for Tools
    run_config = {
        "rag_config": rag_config,
        "google_sheets_url": rag_config.get("google_sheets_url"),
        "rag_session_id": str(session.rag_session_id) if session.rag_session_id else None,
        "client_config": client_config # For is_enterprise flag
    }

    try:
        # Langfuse Context
        lf_user_id = "unknown_user"
        if event_data.sender:
             if event_data.sender.email: lf_user_id = event_data.sender.email
             elif event_data.sender.phone_number: lf_user_id = event_data.sender.phone_number
             elif event_data.sender.name: lf_user_id = event_data.sender.name

        lf_session_id = event_data.conversation_id or "unknown_session"
        langfuse_handler = CallbackHandler()

        # Get Dynamic Model
        llm_settings = await get_llm_config()
        model_name = llm_settings.get("model_name", "gemini-2.0-flash-exp")
        agent_app = get_agent_app(model_name)

        logger.info(f"🤖 Executing Agent with model: {model_name}")

        result = await agent_app.ainvoke(
            initial_state,
            config={
                "callbacks": [langfuse_handler],
                "metadata": {
                    "langfuse_user_id": lf_user_id,
                    "langfuse_session_id": lf_session_id,
                },
                "configurable": run_config
            },
        )
        raw_content = result["messages"][-1].content

        # Handle Structured Content (e.g. Gemini/Anthropic returning list of blocks)
        if isinstance(raw_content, list):
            # Extract text from blocks like [{'type': 'text', 'text': '...'}]
            answer = ""
            for block in raw_content:
                if isinstance(block, dict) and block.get("type") == "text":
                    answer += block.get("text", "")
                else:
                    answer += str(block)
        elif isinstance(raw_content, dict):
            answer = str(raw_content)
        else:
            answer = str(raw_content)

        logger.info(f"✅ Agent Result (Str): {answer[:100]}...")

        # --- 4. Handoff Check ---
        requires_human = False
        for msg in reversed(result["messages"]):
            if isinstance(msg, HumanMessage): break
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc.get("name") == "transfer_to_human":
                        requires_human = True
                        break
            if requires_human: break

        if requires_human:
            logger.info("👨‍💼 Agent requested Handoff.")

        # --- 5. Persist History (Manual Sync) ---
        await _persist_history(db, session, rag_config, user_query, answer)

        return answer, requires_human

    except Exception as e:
        logger.error(f"Agent Execution Failed: {e}", exc_info=True)
        return "I apologize, but I encountered an internal error.", False


async def _persist_history(db: AsyncSession, session: BotSession, rag_config: dict, query: str, answer: str):
    """
    Helper to sync the interaction back to the RAG service history.
    Handles session creation if RAG session does not exist.
    """
    try:
        rag_client = RagClient(
            base_url=rag_config["base_url"],
            api_key=rag_config.get("api_key", ""),
            tenant_id=rag_config["tenant_id"],
        )

        # Ensure RAG ID exists
        if not session.rag_session_id:
             new_id_str = await rag_client.create_session()
             if new_id_str:
                new_uuid = uuid.UUID(new_id_str)
                stmt = update(BotSession).where(BotSession.id == session.id).values(rag_session_id=new_uuid)
                await db.execute(stmt)
                await db.commit()
                session.rag_session_id = new_uuid
                logger.info(f"🆕 Created/Linked RAG Session: {new_uuid}")

        if session.rag_session_id:
            await rag_client.append_message(session.rag_session_id, "user", query)
            await rag_client.append_message(session.rag_session_id, "ai", answer)

    except Exception as e:
        logger.warning(f"Failed to persist history: {e}")
