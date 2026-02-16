import logging
import io
import os
from typing import List

import google.generativeai as genai
from PIL import Image
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.core.config import settings
from app.rag.utils.prompts import IMAGE_DESCRIPTION_PROMPT_TEMPLATE
from app.rag.storage.repository import insert_document_chunk

logger = logging.getLogger(__name__)

# Configure GenAI once
if settings.google_api_key:
    genai.configure(api_key=settings.google_api_key)


def describe_image(image_bytes: bytes, filename: str) -> str:
    """
    Generates a description for an image using Gemini Vision.
    """
    try:
        logger.info(f"Generating caption for image: {filename}")
        # We use a vision-capable model
        model = genai.GenerativeModel("gemini-2.0-flash")
        image = Image.open(io.BytesIO(image_bytes))

        response = model.generate_content([IMAGE_DESCRIPTION_PROMPT_TEMPLATE, image])
        description = response.text
        logger.info(f"Caption generated: {description[:100]}...")
        return description
    except Exception as e:
        logger.error(f"VLM generation failed: {e}")
        return f"Image: {filename} (Description failed)"


async def ingest_document(
    client_id: int, filename: str, content: str = None, file_bytes: bytes = None
):
    """
    Ingests a document (text or image) into the RAG system.
    1. Extract Content (Text or VLM)
    2. Split (RecursiveCharacterTextSplitter)
    3. Embed (GoogleGenerativeAIEmbeddings)
    4. Store (Repository)
    """
    logger.info(f"Ingesting {filename} for client {client_id}")

    is_image = filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))

    if is_image:
        if not file_bytes:
            logger.error("Image ingestion requires file_bytes")
            return

        description = describe_image(file_bytes, filename)
        content = f"[IMAGE DESCRIPTION for {filename}]\n{description}"

    if not content:
        logger.warning(f"No content to ingest for {filename}")
        return

    # 1. Splitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1024,
        chunk_overlap=20,
        length_function=len,
    )
    chunks = splitter.split_text(content)
    logger.info(f"Split into {len(chunks)} chunks")

    # 2. Embeddings
    # Using LangChain's GoogleGenerativeAIEmbeddings
    if not settings.google_api_key:
        logger.error("GOOGLE_API_KEY not set in settings.")
        return

    embeddings_model = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=settings.google_api_key
    )

    # 3. Process Chunks
    try:
        # Batch embedding might be more efficient, but let's do simple loop or batch if supported
        # langchain embeddings.embed_documents takes a list
        vectors = embeddings_model.embed_documents(chunks)
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return

    # 4. Insert
    for chunk_text, vector in zip(chunks, vectors):
        success = await insert_document_chunk(
            client_id, filename, chunk_text, vector
        )
        if not success:
            logger.error(f"Failed to insert chunk for {filename}")

    logger.info(f"Successfully ingested {filename}")
