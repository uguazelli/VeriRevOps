"""RAG domain module."""

from src.modules.rag.ingestion import ingest_document
from src.modules.rag.retrieval import search_documents
from src.modules.rag.service import generate_answer, generate_chatwoot_answer_decision

__all__ = [
    "generate_answer",
    "generate_chatwoot_answer_decision",
    "ingest_document",
    "search_documents",
]
