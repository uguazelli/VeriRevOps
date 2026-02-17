import json
import logging
import uuid

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from bot.agent.prompts import SUMMARY_PROMPT_TEMPLATE
from bot.core.config import settings
from bot.services.global_config_service import get_llm_config

logger = logging.getLogger(__name__)

async def summarize_start_conversation(
    session_id: uuid.UUID,
    start_time: str = None,
    language_instruction: str = None
) -> dict:
    """Fetches chat history from internal DB and generates a structured summary using Gemini.
    """
    try:
        # 1. Fetch History
        # We use the internal service function
        from rag.services.rag_service import get_chat_history
        history_data = await get_chat_history(session_id, limit=50) # Fetch more context for summary

        if not history_data:
            logger.warning("No history found for summarization.")
            return {}

        # Format history for prompt
        history_str = ""
        first_msg_time = None

        for msg in history_data:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            # Internal history doesn't strictly return timestamp in the dict currently (just role/content)
            # unless we modify get_chat_history. For now, we skip timestamp extraction from messages.

            history_str += f"{role.upper()}: {content}\n"

        # 2. Prepare Prompt
        lang_instr = f"IMPORTANT: Detected Language Override: {language_instruction}" if language_instruction else ""

        prompt = SUMMARY_PROMPT_TEMPLATE.format(
            history_str=history_str,
            language_instruction=lang_instr
        )

        # 3. Call LLM
        # Fetch dynamic config using contextualization model for summarization
        config = await get_llm_config()
        model_name = config["steps"]["contextualization"]["model"]

        model = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            google_api_key=settings.google_api_key,
        )

        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="Analyze the conversation now.")
        ]

        response = await model.ainvoke(messages)
        content = response.content.replace("```json", "").replace("```", "").strip()

        # 4. Parse JSON
        try:
            summary_data = json.loads(content)
            # Inject start time availability check
            if first_msg_time:
                 summary_data["session_start_time"] = first_msg_time
            return summary_data

        except json.JSONDecodeError:
            logger.error(f"Failed to parse summary JSON: {content}")
            return {"ai_summary": content} # Fallback

    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        return {}
