from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field, Relationship, Column, UniqueConstraint
from sqlalchemy import Integer, String, Boolean, BigInteger, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

# --- GLOBAL CONFIG ---
class GlobalConfigBase(SQLModel):
    settings: Optional[dict] = Field(default=None, sa_column=Column(JSONB))

class GlobalConfig(GlobalConfigBase, table=True):
    __tablename__ = "global_configs"
    id: Optional[int] = Field(default=None, primary_key=True)

class GlobalConfigCreate(GlobalConfigBase):
    pass

class GlobalConfigUpdate(GlobalConfigBase):
    pass

class GlobalConfigResponse(GlobalConfigBase):
    id: int


# --- TENANT ---
class TenantBase(SQLModel):
    slug: str = Field(sa_column=Column(String(255), nullable=False, unique=True))
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime(timezone=True)))

class Tenant(TenantBase, table=True):
    __tablename__ = "tenants"
    id: Optional[int] = Field(default=None, primary_key=True)

    subscriptions: List["Subscription"] = Relationship(back_populates="tenant", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    configurations: List["Configuration"] = Relationship(back_populates="tenant", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    services: List["Service"] = Relationship(back_populates="tenant", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    contact_mappings: List["ContactMapping"] = Relationship(back_populates="tenant", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    chat_messages: List["ChatMessage"] = Relationship(back_populates="tenant", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    documents: List["Document"] = Relationship(back_populates="tenant", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

# --- SUBSCRIPTION ---
class SubscriptionBase(SQLModel):
    tenant_id: int = Field(foreign_key="tenants.id", ondelete="CASCADE")
    is_active: bool = Field(default=True)
    quota_limit: int = Field(default=0, sa_column=Column(BigInteger, default=0, nullable=False))
    usage_count: int = Field(default=0, sa_column=Column(BigInteger, default=0, nullable=False))
    start_dat: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    end_date: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))

class Subscription(SubscriptionBase, table=True):
    __tablename__ = "subscriptions"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant: Optional["Tenant"] = Relationship(back_populates="subscriptions")

class SubscriptionResponse(SubscriptionBase):
    id: int

# --- CONFIGURATION ---
class ConfigurationBase(SQLModel):
    tenant_id: int = Field(foreign_key="tenants.id", ondelete="CASCADE")
    settings: Optional[dict] = Field(default=None, sa_column=Column(JSONB))

class Configuration(ConfigurationBase, table=True):
    __tablename__ = "configurations"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant: Optional["Tenant"] = Relationship(back_populates="configurations")

class ConfigurationResponse(ConfigurationBase):
    id: int

# --- SERVICE ---
class ServiceBase(SQLModel):
    tenant_id: int = Field(foreign_key="tenants.id", ondelete="CASCADE")
    name: str = Field(max_length=255)
    url: Optional[str] = Field(default=None, max_length=255)
    api_key: Optional[str] = Field(default=None, max_length=255)
    account_id: Optional[str] = Field(default=None, max_length=255)
    settings: Optional[dict] = Field(default=None, sa_column=Column(JSONB))

class Service(ServiceBase, table=True):
    __tablename__ = "services"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant: Optional["Tenant"] = Relationship(back_populates="services")

class ServiceResponse(ServiceBase):
    id: int

# --- TENANT RESPONSES ---
class TenantResponse(TenantBase):
    id: int
    services: Dict[str, ServiceResponse] = {}
    subscription: Optional[SubscriptionResponse] = None
    configuration: Optional[ConfigurationResponse] = None

class TenantFullResponse(SQLModel):
    tenant: TenantResponse
    global_config: Optional[GlobalConfigResponse] = None

# --- CONTACT MAPPING ---
class ContactMappingBase(SQLModel):
    tenant_id: int = Field(foreign_key="tenants.id", ondelete="CASCADE")
    chatwoot_contact_id: int
    service_name: str = Field(max_length=255)
    external_id: str = Field(max_length=255)

class ContactMapping(ContactMappingBase, table=True):
    __tablename__ = "contact_mappings"
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant: Optional["Tenant"] = Relationship(back_populates="contact_mappings")

class ContactMappingCreate(ContactMappingBase):
    pass

class ContactMappingUpdate(SQLModel):
    tenant_id: int
    service_name: str
    external_id: str

class ContactMappingResponse(ContactMappingBase):
    id: int

# --- CHAT MESSAGE ---
class ChatMessageBase(SQLModel):
    tenant_id: int = Field(foreign_key="tenants.id", ondelete="CASCADE")
    chatwoot_account_id: int
    chatwoot_conversation_id: int
    message_id: int
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime(timezone=True)))

class ChatMessage(ChatMessageBase, table=True):
    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("tenant_id", "chatwoot_account_id", "chatwoot_conversation_id", name="uq_chat_message_conversation"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant: Optional["Tenant"] = Relationship(back_populates="chat_messages")

class ChatMessageCreate(SQLModel):
    tenant_id: int
    chatwoot_account_id: int
    chatwoot_conversation_id: int
    message_id: int

class ChatMessageResponse(ChatMessageBase):
    id: int

# --- DOCUMENT ---
class Document(SQLModel, table=True):
    __tablename__ = "documents"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.id", ondelete="CASCADE")
    parent_id: Optional[uuid.UUID] = Field(default=None, foreign_key="documents.id", ondelete="CASCADE")
    filename: str = Field(max_length=255)
    content: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime(timezone=True)))

    tenant: Optional["Tenant"] = Relationship(back_populates="documents")
