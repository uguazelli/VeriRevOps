from datetime import datetime
from typing import List, Optional
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, Text, Float, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

class Base(DeclarativeBase):
    pass

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    subscriptions: Mapped[List["Subscription"]] = relationship(back_populates="tenant")
    chat_sessions: Mapped[List["ChatSession"]] = relationship(back_populates="tenant")
    rag_files: Mapped[List["RagFile"]] = relationship(back_populates="tenant")

class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    quota_limit: Mapped[int] = mapped_column(Integer)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

    tenant: Mapped["Tenant"] = relationship(back_populates="subscriptions")

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="chat_sessions")
    messages: Mapped[List["ChatMessage"]] = relationship(back_populates="session")

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    session: Mapped["ChatSession"] = relationship(back_populates="messages")

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