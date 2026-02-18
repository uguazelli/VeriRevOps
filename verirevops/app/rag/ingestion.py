import os
from typing import List
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.database import execute_write_query
from app.core.queries import INSERT_RAG_CHUNK
import json

# Initialize embeddings
# Ensure GOOGLE_API_KEY is set in .env
embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len,
)

async def ingest_file_content(file_id: int, content: str):
    """
    Splits content into chunks, generates embeddings, and saves to DB.
    """
    chunks = text_splitter.split_text(content)

    # Generate embeddings for all chunks
    # Note: embed_documents takes a list of strings
    vectors = embeddings.embed_documents(chunks)

    for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
        # Convert vector list to string representation for pgvector if needed,
        # but psycopg2 usually handles lists if registered, or we cast it.
        # pgvector expects a string like '[0.1, 0.2, ...]' or a list if adapter is set.
        # We'll stick to passing the list and letting the driver handle it or casting to string.
        # Safest for raw SQL is often a string format.

        # Metadata can be expanded later
        metadata = json.dumps({"chunk_index": i})

        execute_write_query(INSERT_RAG_CHUNK, (file_id, i, chunk, str(vector), metadata))

    return len(chunks)

async def embed_query(text: str) -> List[float]:
    """
    Generates an embedding for a query string.
    """
    return await embeddings.aembed_query(text)
