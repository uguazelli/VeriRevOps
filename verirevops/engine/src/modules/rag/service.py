import json
import logging

from src.core.logging import log_error, log_start
from src.core.prompts import CHATWOOT_RAG_RESPONSE_PROMPT, RAG_SYSTEM_PROMPT
from src.modules.ai.factory import get_llm
from src.modules.rag.retrieval import search_documents


logger = logging.getLogger(__name__)

MIN_CHATWOOT_RAG_CONFIDENCE = 0.75


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


async def generate_chatwoot_answer_decision(
    tenant_id: int,
    message: str,
    provider: str = "gemini",
) -> dict:
    """
    Generate a guarded Chatwoot answer decision.

    The returned shape is always a dict containing data.answer, data.confidence,
    data.allowed_to_answer, data.handoff_required, and data.clear_source.
    """
    log_start(
        logger,
        f"Generating guarded Chatwoot answer for message: '{message[:50]}...' | Provider={provider}",
    )

    results = await search_documents(
        tenant_id,
        message,
        use_rerank=True,
        provider=provider,
    )

    if not has_clear_rag_context(results):
        return build_chatwoot_handoff_decision(
            "No clear approved knowledge-base source was found for this question."
        )

    context_str = "\n\n".join(
        [
            f"Source: {result['filename']}\n{result['content']}"
            for result in results
            if result.get("filename") and result.get("content")
        ]
    )
    prompt = CHATWOOT_RAG_RESPONSE_PROMPT.format(
        context_str=context_str,
        message=message,
    )

    try:
        llm = get_llm(provider)
        response = await llm.acomplete(prompt)
        decision = parse_chatwoot_answer_decision(response.text)
    except Exception as exc:
        log_error(logger, f"Guarded Chatwoot answer generation failed: {exc}")
        return build_chatwoot_handoff_decision("The assistant could not verify a safe answer.")

    if should_handoff_chatwoot_answer(decision):
        return force_chatwoot_handoff_decision(decision)

    return decision


def has_clear_rag_context(results) -> bool:
    if not results:
        return False

    return any(
        isinstance(result, dict)
        and bool(result.get("filename"))
        and bool(result.get("content"))
        for result in results
    )


def parse_chatwoot_answer_decision(raw_response: str) -> dict:
    response_text = raw_response.strip()

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        start = response_text.find("{")
        end = response_text.rfind("}")

    if start != -1 and end != -1 and start < end:
        try:
            return json.loads(response_text[start:end + 1])
        except json.JSONDecodeError:
            pass

    logger.error("Failed to parse guarded Chatwoot answer JSON: %s", raw_response)
    return build_chatwoot_handoff_decision("The assistant could not parse a safe answer decision.")


def should_handoff_chatwoot_answer(decision: dict) -> bool:
    data = get_chatwoot_answer_data(decision)

    if data.get("handoff_required") is True:
        return True

    if data.get("allowed_to_answer") is not True:
        return True

    if data.get("clear_source") is not True:
        return True

    if get_chatwoot_answer_confidence(data) < MIN_CHATWOOT_RAG_CONFIDENCE:
        return True

    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        return True

    answer = data.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        return True

    return False


def get_chatwoot_answer_data(decision: dict) -> dict:
    if not isinstance(decision, dict):
        return {}

    data = decision.get("data")
    if not isinstance(data, dict):
        return {}

    return data


def get_chatwoot_answer_confidence(data: dict) -> float:
    try:
        return float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        return 0.0


def force_chatwoot_handoff_decision(decision: dict) -> dict:
    data = get_chatwoot_answer_data(decision)
    reason = data.get("reason") or "The answer requires human review."

    return build_chatwoot_handoff_decision(reason)


def build_chatwoot_handoff_decision(reason: str) -> dict:
    return {
        "data": {
            "answer": "",
            "confidence": 0.0,
            "allowed_to_answer": False,
            "handoff_required": True,
            "clear_source": False,
            "reason": reason,
            "sources": [],
        }
    }
