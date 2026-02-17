import io
import logging

from google import genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from PIL import Image

from bot.core.config import settings
from bot.services.global_config_service import get_llm_config
from rag.storage.repository import insert_document_chunk
from rag.utils.prompts import IMAGE_DESCRIPTION_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)

def get_genai_client():
    if not settings.google_api_key:
        return None
    return genai.Client(api_key=settings.google_api_key)


def describe_image(image_bytes: bytes, filename: str, model_name: str) -> str:
    """Generates a description for an image using Gemini Vision (google-genai SDK).
    """
    client = get_genai_client()
    if not client:
        logger.error("Google AI Client could not be initialized (missing API key).")
        return f"Image: {filename} (Config error)"

    try:
        logger.info(f"Generating caption for image: {filename} using {model_name}")
        image = Image.open(io.BytesIO(image_bytes))

        # New SDK uses client.models.generate_content
        response = client.models.generate_content(
            model=model_name,
            contents=[IMAGE_DESCRIPTION_PROMPT_TEMPLATE, image]
        )
        description = response.text
        logger.info(f"Caption generated: {description[:100]}...")
        return description
    except Exception as e:
        logger.error(f"VLM generation failed: {e}")
        return f"Image: {filename} (Description failed)"


async def ingest_document(
    client_id: int, filename: str, content: str = None, file_bytes: bytes = None
):
    """Ingests a document (text or image) into the RAG system.
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

        try:
            # Fetch config for VLM - using generation model as it usually supports vision
            config = await get_llm_config()
            vlm_model = config["steps"]["generation"]["model"]

            description = describe_image(file_bytes, filename, vlm_model)
            content = f"[IMAGE DESCRIPTION for {filename}]\n{description}"
        except Exception as e:
            logger.error(f"Failed to get config or generate description: {e}")
            return

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
