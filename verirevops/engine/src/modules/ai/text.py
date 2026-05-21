import asyncio
import logging

from src.core.logging import log_error, log_start, log_success
from src.modules.ai.factory import get_text_llm


logger = logging.getLogger(__name__)


async def get_chat_response(message: str, provider: str = "gemini") -> str:
    """
    Generate a direct LLM completion without RAG.
    """
    log_start(logger, f"Direct completion for message: '{message[:50]}...' | Provider={provider}")

    try:
        llm = get_text_llm(provider)
        response = await asyncio.to_thread(llm.complete, message)
        answer = response.text
        log_success(logger, "Direct completion successful")
        return answer
    except Exception as exc:
        log_error(logger, f"Direct completion failed: {exc}")
        return "Sorry, I encountered an error while processing your request."
