import logging

from src.core.llm_factory import get_llm
from src.core.logging import log_error, log_start
from src.core.prompts import RAG_SYSTEM_PROMPT
from src.modules.rag.retrieval import search_documents


logger = logging.getLogger(__name__)


async def generate_answer(
    tenant_id: int,
    message: str,
    provider: str = "gemini",
) -> str:
    """
    Retrieves tenant context and generates an answer using the requested LLM provider.
    """
    log_start(logger, f"Generating answer for message: '{message[:50]}...' | Provider={provider}")

    results = await search_documents(
        tenant_id,
        message,
        use_rerank=True,
        provider=provider,
    )

    if not results:
        context_str = "No relevant documents found."
    else:
        context_str = "\n\n".join([
            f"Source: {result['filename']}\n{result['content']}"
            for result in results
        ])

    prompt = RAG_SYSTEM_PROMPT.format(context_str=context_str, message=message)

    try:
        llm = get_llm(provider)
        response = await llm.acomplete(prompt)
        return response.text
    except Exception as exc:
        log_error(logger, f"LLM generation failed: {exc}")
        return "Sorry, I encountered an error generating the answer."

