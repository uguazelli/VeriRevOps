import json
import logging
from typing import Any, Dict, List

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from bot.core.ai import get_llm
from bot.services.global_config_service import get_llm_config
from utils.prompts import RERANK_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)

async def get_rerank_chain():
    """Returns an LCEL chain for scoring a SINGLE document."""

    # Fetch dynamic config
    config = await get_llm_config()
    model_name = config["steps"]["rag_search"]["model"]

    llm = get_llm(model_name=model_name, temperature=0.0) # Strict scoring

    prompt = PromptTemplate.from_template(RERANK_PROMPT_TEMPLATE)

    def parse_score(output: str) -> int:
        try:
            text = output.replace("```json", "").replace("```", "").strip()
            score_data = json.loads(text)
            return int(score_data.get("score", 0))
        except Exception as e:
            logger.warning(f"Reranking parse failed: {e}")
            return 0

    chain = (
        prompt
        | llm
        | StrOutputParser()
        | parse_score
    )

    return chain

async def rerank_documents_lcel(query: str, documents: List[Dict[str, Any]], top_k: int = 5, min_score: float = 7.0) -> List[Dict[str, Any]]:
    """Orchestrates the reranking chain across multiple documents."""

    chain = await get_rerank_chain()

    scored_docs = []
    dropped_count = 0

    # We can use ainvoke on the chain for each doc
    # For now, sequential loop to be safe with rate limits, or we could use batch/gather
    for doc in documents:
        try:
            content_preview = doc["content"][:1000]
            score = await chain.ainvoke({"query": query, "content": content_preview})

            if score >= min_score:
                doc["rerank_score"] = score
                scored_docs.append(doc)
            else:
                dropped_count += 1

        except Exception as e:
            logger.warning(f"Reranking failed for doc {doc.get('id')}: {e}")
            dropped_count += 1

    scored_docs.sort(key=lambda x: x["rerank_score"], reverse=True)

    logger.info(f"⚖️ Reranker (LCEL): Kept {len(scored_docs)} docs (Dropping {dropped_count} below score {min_score})")

    return scored_docs[:top_k]
