import os
import logging
import json
import warnings
import logging as py_logging
from typing import List, Dict, Any

from llama_index.core.postprocessor import LLMRerank
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.core import QueryBundle

from src.core.llm_factory import get_llm

logger = logging.getLogger(__name__)

def rerank_documents(query: str, documents: List[Dict[str, Any]], top_k: int = 5, provider: str = "gemini") -> List[Dict[str, Any]]:
    """
    Reranks a list of documents based on semantic relevance to the query using an LLM.
    Returns the top K documents.
    """
    if not documents:
        return []

    logger.info(f"Reranking {len(documents)} documents using API-based LLM ({provider})")

    try:
        # Initialize the API-based reranker
        llm = get_llm(provider)
        reranker = LLMRerank(
            llm=llm,
            top_n=top_k
        )

        # Convert dictionary documents to LlamaIndex Nodes
        nodes_with_scores = []
        for doc in documents:
            node = TextNode(
                text=doc['content'],
                metadata={"id": doc['id'], "filename": doc.get('filename', '')}
            )
            # Give initial score from RRF or original retrieval
            nodes_with_scores.append(NodeWithScore(node=node, score=doc.get('distance', 1.0)))

        query_bundle = QueryBundle(query_str=query)

        # Perform the actual reranking
        reranked_nodes = reranker.postprocess_nodes(nodes_with_scores, query_bundle=query_bundle)

        # Convert back to our dictionary format
        scored_docs = []
        for ranked_node in reranked_nodes:
            # Reconstruct the dict
            doc_dict = {
                "id": ranked_node.node.metadata.get("id"),
                "filename": ranked_node.node.metadata.get("filename"),
                "content": ranked_node.node.get_content(),
                # Map the cross-encoder logit score
                "rerank_score": ranked_node.score
            }
            scored_docs.append(doc_dict)

        return scored_docs

    except Exception as e:
        logger.error(f"API-based Reranking failed: {e}. Falling back to original retrieval order.")
        # If it fails, just return the original documents up to top_k
        return documents[:top_k]
