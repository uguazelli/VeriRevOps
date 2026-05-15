import json
import logging
import os

from llama_index.core import Document, SimpleDirectoryReader
from llama_index.core.extractors import SummaryExtractor, TitleExtractor
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SemanticSplitterNodeParser
from sqlalchemy import text

from src.core.db import get_session
from src.core.queries import INSERT_PARENT_DOCUMENT_QUERY
from src.modules.ai.factory import get_llm
from src.modules.ai.vision import describe_image
from src.modules.rag.embeddings import get_embed_model


logger = logging.getLogger(__name__)


async def ingest_document(
    tenant_id: int,
    filename: str,
    content: str = None,
    file_bytes: bytes = None,
    temp_file_path: str = None,
):
    """
    Parses, chunks, embeds, and inserts a tenant document into the database.
    """
    logger.info("Ingesting document %s for tenant %s", filename, tenant_id)

    docs = []

    if temp_file_path:
        try:
            reader = SimpleDirectoryReader(input_files=[temp_file_path])
            docs = reader.load_data()

            for document in docs:
                document.metadata["filename"] = filename
                document.metadata["tenant_id"] = str(tenant_id)
                document.metadata["original_type"] = "document"
        except Exception as exc:
            logger.error("Error parsing document %s: %s", filename, exc)
            return
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    else:
        is_image = filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))

        if is_image:
            if not file_bytes:
                logger.error("Image ingestion requires file_bytes")
                return
            logger.info("Processing image with VLM...")
            content = describe_image(file_bytes, filename)
            content = f"[IMAGE DESCRIPTION for {filename}]\n{content}"

        if not content:
            logger.warning("No content to ingest for %s", filename)
            return

        docs = [
            Document(
                text=content,
                metadata={
                    "filename": filename,
                    "tenant_id": str(tenant_id),
                    "original_type": "image" if is_image else "text",
                },
            )
        ]

    if not docs:
        logger.warning("No documents were loaded from %s", filename)
        return

    llm = get_llm("gemini")
    embed_model = get_embed_model()

    pipeline = IngestionPipeline(
        transformations=[
            SemanticSplitterNodeParser(
                buffer_size=1,
                breakpoint_percentile_threshold=95,
                embed_model=embed_model,
            ),
            TitleExtractor(llm=llm, nodes=5),
            SummaryExtractor(llm=llm, summaries=["prev", "self"]),
        ]
    )

    logger.info("Running metadata extraction pipeline...")
    try:
        nodes = await pipeline.arun(documents=docs)
    except Exception as exc:
        logger.error("Pipeline extraction failed: %s", exc)
        return

    logger.info("Split into %s chunks with metadata", len(nodes))

    texts = [node.get_content() for node in nodes]
    try:
        embeddings = embed_model.get_text_embedding_batch(texts)
    except Exception as exc:
        logger.error("Embedding failed: %s", exc)
        return

    async with get_session() as session:
        full_content = "\n\n".join([document.get_content() for document in docs])
        parent_meta = docs[0].metadata if docs else {}

        cursor = await session.execute(
            text(INSERT_PARENT_DOCUMENT_QUERY),
            {
                "tenant": tenant_id,
                "file": filename,
                "content": full_content,
                "meta": json.dumps(parent_meta),
            },
        )
        parent_id = cursor.scalar()

        for node, embedding in zip(nodes, embeddings):
            metadata_json = json.dumps(node.metadata)
            await session.execute(
                text(
                    "INSERT INTO documents "
                    "(tenant_id, filename, content, embedding, metadata_, parent_id) "
                    "VALUES (:tenant, :file, :content, :emb, :meta, :pid)"
                ),
                {
                    "tenant": tenant_id,
                    "file": filename,
                    "content": node.get_content(),
                    "emb": str(embedding),
                    "meta": metadata_json,
                    "pid": parent_id,
                },
            )
        await session.commit()

    logger.info("Successfully ingested %s", filename)
