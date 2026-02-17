import logging
from bot.core.config import settings
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

logger = logging.getLogger(__name__)

def get_llm(model_name: str, temperature: float = 0.0) -> ChatGoogleGenerativeAI:
    """Factory to create a configured ChatGoogleGenerativeAI client."""
    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY is not set.")

    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=settings.google_api_key,
        temperature=temperature,
    )

def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """Factory to create a configured GoogleGenerativeAIEmbeddings client."""
    if not settings.google_api_key:
        raise ValueError("GOOGLE_API_KEY is not set.")

    return GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=settings.google_api_key
    )
