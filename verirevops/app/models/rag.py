from datetime import datetime
from typing import List
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from app.models.base import Base

class RagFile(Base):
    __tablename__ = "rag_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    filename: Mapped[str] = mapped_column(String, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    tenant: Mapped["Tenant"] = relationship(back_populates="rag_files")
    chunks: Mapped[List["RagChunk"]] = relationship(back_populates="file", cascade="all, delete-orphan")

class RagChunk(Base):
    __tablename__ = "rag_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("rag_files.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Using 3072 dimensions as per current Google Embedding model
    embedding: Mapped[List[float]] = mapped_column(Vector(3072))
    # Rename python attribute to avoid conflict with SQLAlchemy metadata
    chunk_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default={})

    file: Mapped["RagFile"] = relationship(back_populates="chunks")
