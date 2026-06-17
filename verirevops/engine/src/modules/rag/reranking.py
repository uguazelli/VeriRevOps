import logging
from typing import Any

from llama_index.core import QueryBundle
from llama_index.core.postprocessor import LLMRerank
from llama_index.core.schema import NodeWithScore, TextNode

from src.modules.ai.factory import build_fresh_text_llm


logger = logging.getLogger(__name__)


def rerank_documents(
    query: str,
    documents: list[dict[str, Any]],
    top_k: int = 5,
    provider: str = "gemini",
) -> list[dict[str, Any]]:
    """
    Reranks documents based on semantic relevance to the query using an LLM.
    """
    if not documents:
        return []

    logger.info("Reranking %s documents using API-based LLM (%s)", len(documents), provider)

    try:
        llm = build_fresh_text_llm(provider)
        reranker = LLMRerank(
            llm=llm,
            top_n=top_k,
        )

        nodes_with_scores = []
        for document in documents:
            node = TextNode(
                text=document["content"],
                metadata={
                    "id": document["id"],
                    "filename": document.get("filename", ""),
                },
            )
            nodes_with_scores.append(
                NodeWithScore(node=node, score=document.get("distance", 1.0))
            )

        query_bundle = QueryBundle(query_str=query)
        reranked_nodes = reranker.postprocess_nodes(
            nodes_with_scores,
            query_bundle=query_bundle,
        )

        scored_documents = []
        for ranked_node in reranked_nodes:
            scored_documents.append({
                "id": ranked_node.node.metadata.get("id"),
                "filename": ranked_node.node.metadata.get("filename"),
                "content": ranked_node.node.get_content(),
                "rerank_score": ranked_node.score,
            })

        return scored_documents

    except Exception as exc:
        logger.error(
            "API-based reranking failed: %s. Falling back to original retrieval order.",
            exc,
        )
        return documents[:top_k]
