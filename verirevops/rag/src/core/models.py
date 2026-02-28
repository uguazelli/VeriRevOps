from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Boolean, BigInteger, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

class Base(DeclarativeBase):
    pass

class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    subscriptions: Mapped[List["Subscription"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    configurations: Mapped[List["Configuration"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    services: Mapped[List["Service"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    contact_mappings: Mapped[List["ContactMapping"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    chat_sessions: Mapped[List["ChatSession"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")
    documents: Mapped[List["Document"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")

    def __str__(self):
        return f"Tenant({self.id}, {self.slug})"

class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quota_limit: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    usage_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    start_dat: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="subscriptions")

class Configuration(Base):
    __tablename__ = "configurations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    settings: Mapped[Optional[dict]] = mapped_column(JSONB)

    tenant: Mapped["Tenant"] = relationship(back_populates="configurations")

class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(255))
    api_key: Mapped[Optional[str]] = mapped_column(String(255))
    account_id: Mapped[Optional[str]] = mapped_column(String(255))
    settings: Mapped[Optional[dict]] = mapped_column(JSONB)

    tenant: Mapped["Tenant"] = relationship(back_populates="services")

class ContactMapping(Base):
    __tablename__ = "contact_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    chatwoot_contact_id: Mapped[int] = mapped_column(Integer, nullable=False)
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="contact_mappings")

class ChatSession(Base):
    __tablename__ = "chat_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    last_summarized_message_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_private_summarized_message_id: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chatwoot_account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    chatwoot_conversation_id: Mapped[int] = mapped_column(Integer, nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="chat_sessions")

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # embedding is handled by pgvector, which SQLAlchemy can handle via custom types if needed,
    # but for CRUD we might just want to see it exists or skip it.
    # For now, we skip embedding in CRUD if it's too complex, or use a generic Type.
    # We won't add embedding here to avoid pgvector dependency in models for now.

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    tenant: Mapped["Tenant"] = relationship(back_populates="documents")
