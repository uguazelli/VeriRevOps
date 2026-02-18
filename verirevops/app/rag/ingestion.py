import os
from typing import List
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


# Initialize embeddings
api_key = os.getenv("GOOGLE_API_KEY")
embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", google_api_key=api_key)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len,
)

from sqlalchemy.ext.asyncio import AsyncSession
from app.models import RagChunk

async def ingest_file_content(session: AsyncSession, file_id: int, content: str):
    """
    Splits content into chunks, generates embeddings, and saves to DB using ORM.
    """
    chunks = text_splitter.split_text(content)

    # Generate embeddings for all chunks
    vectors = embeddings.embed_documents(chunks)

    # Prepare RagChunk objects
    rag_chunks = []
    for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
        rag_chunk = RagChunk(
            file_id=file_id,
            chunk_index=i,
            content=chunk,
            embedding=vector,
            chunk_metadata={"chunk_index": i}
        )
        rag_chunks.append(rag_chunk)

    # Bulk insert for performance (or add_all)
    session.add_all(rag_chunks)
    await session.commit()

    return len(chunks)

async def embed_query(text: str) -> List[float]:
    """
    Generates an embedding for a query string.
    """
    return await embeddings.aembed_query(text)
