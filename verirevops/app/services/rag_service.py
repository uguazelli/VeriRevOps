from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models import RagFile
from app.rag.ingestion import ingest_file_content
from app.rag.retrieve import invoke_rag_graph
from app.core.logger import Log

class RagService:
    def __init__(self, db: AsyncSession):
        self.db = db


    async def ingest_file(self, tenant_id: int, filename: str, content: str):
        """Register and process a RAG file."""
        try:
            # 1. Register the file
            new_file = RagFile(tenant_id=tenant_id, filename=filename)
            self.db.add(new_file)
            await self.db.commit()
            await self.db.refresh(new_file)

            # 2. Ingest (Chunk & Embed)
            num_chunks = await ingest_file_content(self.db, new_file.id, content)
            Log.success(f"File '{filename}' ingested for Tenant {tenant_id} ({num_chunks} chunks)")
            return new_file.id, num_chunks
        except Exception as e:
            await self.db.rollback()
            Log.error(f"Failed to ingest file: {e}")
            raise e


    async def list_tenant_files(self, tenant_id: int):
        """List all RAG files for a specific tenant."""
        stmt = select(RagFile).where(RagFile.tenant_id == tenant_id).order_by(RagFile.uploaded_at.desc())
        result = await self.db.execute(stmt)
        return result.scalars().all()


    async def delete_file(self, file_id: int):
        """Remove a RAG file and its chunks."""
        file = await self.db.get(RagFile, file_id)
        if not file:
            return False

        await self.db.delete(file)
        await self.db.commit()
        Log.info(f"Deleted RAG file {file_id}")
        return True


    async def perform_search(self, session_id: int, tenant_id: int, query: str):
        """Perform a RAG search using the orchestrator graph."""
        try:
            answer = await invoke_rag_graph(session_id, query, self.db, tenant_id)
            return answer
        except Exception as e:
            Log.error(f"RAG Service Search Error: {e}")
            raise e
