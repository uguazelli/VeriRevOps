import logging
from src.core.llm_factory import get_llm
from src.core.logging import log_start, log_success, log_error

logger = logging.getLogger(__name__)

async def get_chat_response(message: str, provider: str = "gemini") -> str:
    """
    Generates a completion directly from the LLM, bypassing RAG.
    """
    log_start(logger, f"Direct completion for message: '{message[:50]}...' | Provider={provider}")

    try:
        llm = get_llm(provider)
        # Using complete() for a single prompt/response interaction
        response = llm.complete(message)
        answer = response.text
        log_success(logger, f"Direct completion successful")
        return answer
    except Exception as e:
        log_error(logger, f"Direct completion failed: {e}")
        return "Sorry, I encountered an error while processing your request."
