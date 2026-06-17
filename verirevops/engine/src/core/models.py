from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, Relationship, SQLModel, UniqueConstraint


JSONDict = dict[str, Any]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# --- GLOBAL CONFIG ---
class GlobalConfigBase(SQLModel):
    settings: JSONDict | None = Field(default=None, sa_column=Column(JSONB))


class GlobalConfig(GlobalConfigBase, table=True):
    __tablename__ = "global_configs"
    id: int | None = Field(default=None, primary_key=True)

    def __str__(self) -> str:
        return f"global_config:{self.id}"


# --- TENANT ---
class TenantBase(SQLModel):
    slug: str = Field(sa_column=Column(String(255), nullable=False, unique=True))
    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True))
    )


class Tenant(TenantBase, table=True):
    __tablename__ = "tenants"
    id: int | None = Field(default=None, primary_key=True)

    subscriptions: list["Subscription"] = Relationship(
        back_populates="tenant", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    configurations: list["Configuration"] = Relationship(
        back_populates="tenant", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    services: list["Service"] = Relationship(
        back_populates="tenant", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    contact_mappings: list["ContactMapping"] = Relationship(
        back_populates="tenant", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    chat_messages: list["ChatMessage"] = Relationship(
        back_populates="tenant", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    documents: list["Document"] = Relationship(
        back_populates="tenant", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    users: list["User"] = Relationship(
        back_populates="tenant", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    invitations: list["Invitation"] = Relationship(
        back_populates="tenant", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )

    def __str__(self) -> str:
        return f"{self.slug}#{self.id}"


# --- USER ---
class User(SQLModel, table=True):
    __tablename__ = "users"
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(sa_column=Column(String(255), nullable=False, unique=True))
    hashed_password: str = Field(sa_column=Column(String(255), nullable=False))
    full_name: str | None = Field(default=None, max_length=255)
    # Roles: "superadmin", "tenant_admin", "tenant_member"
    role: str = Field(default="tenant_admin", sa_column=Column(String(50), nullable=False))
    tenant_id: int | None = Field(default=None, foreign_key="tenants.id", ondelete="CASCADE")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True))
    )

    tenant: Tenant | None = Relationship(back_populates="users")

    def __str__(self) -> str:
        return f"user:{self.email}#{self.id} role:{self.role}"


# --- INVITATION ---
class Invitation(SQLModel, table=True):
    __tablename__ = "invitations"
    id: int | None = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.id", ondelete="CASCADE")
    email: str = Field(sa_column=Column(String(255), nullable=False))
    token: str = Field(sa_column=Column(String(255), nullable=False, unique=True))
    role: str = Field(default="tenant_member", sa_column=Column(String(50), nullable=False))
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    accepted_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_by_id: int = Field(foreign_key="users.id")
    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True))
    )

    tenant: Tenant | None = Relationship(back_populates="invitations")

    def __str__(self) -> str:
        return f"invitation:{self.email} tenant:{self.tenant_id} role:{self.role}"


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
    id: int | None = Field(default=None, primary_key=True)
    tenant: Tenant | None = Relationship(back_populates="subscriptions")

    def __str__(self) -> str:
        return f"subscription:{self.id} tenant:{self.tenant_id} active:{self.is_active}"


# --- CONFIGURATION ---
class ConfigurationBase(SQLModel):
    tenant_id: int = Field(foreign_key="tenants.id", ondelete="CASCADE")
    settings: JSONDict | None = Field(default=None, sa_column=Column(JSONB))


class Configuration(ConfigurationBase, table=True):
    __tablename__ = "configurations"
    id: int | None = Field(default=None, primary_key=True)
    tenant: Tenant | None = Relationship(back_populates="configurations")

    def __str__(self) -> str:
        return f"configuration:{self.id} tenant:{self.tenant_id}"


# --- SERVICE ---
class ServiceBase(SQLModel):
    tenant_id: int = Field(foreign_key="tenants.id", ondelete="CASCADE")
    name: str = Field(max_length=255)
    url: str | None = Field(default=None, max_length=255)
    api_key: str | None = Field(default=None, max_length=255)
    account_id: str | None = Field(default=None, max_length=255)
    settings: JSONDict | None = Field(default=None, sa_column=Column(JSONB))


class Service(ServiceBase, table=True):
    __tablename__ = "services"
    id: int | None = Field(default=None, primary_key=True)
    tenant: Tenant | None = Relationship(back_populates="services")

    def __str__(self) -> str:
        account = self.account_id or "-"
        return f"service:{self.name}#{self.id} tenant:{self.tenant_id} account:{account}"


# --- CONTACT MAPPING ---
class ContactMappingBase(SQLModel):
    tenant_id: int = Field(foreign_key="tenants.id", ondelete="CASCADE")
    chatwoot_contact_id: int
    service_name: str = Field(max_length=255)
    external_id: str = Field(max_length=255)


class ContactMapping(ContactMappingBase, table=True):
    __tablename__ = "contact_mappings"
    id: int | None = Field(default=None, primary_key=True)
    tenant: Tenant | None = Relationship(back_populates="contact_mappings")

    def __str__(self) -> str:
        return (
            f"mapping:{self.service_name}#{self.id} "
            f"chatwoot:{self.chatwoot_contact_id} external:{self.external_id}"
        )


# --- CHAT MESSAGE ---
class ChatMessageBase(SQLModel):
    tenant_id: int = Field(foreign_key="tenants.id", ondelete="CASCADE")
    chatwoot_account_id: int
    chatwoot_conversation_id: int
    message_id: int
    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True))
    )


class ChatMessage(ChatMessageBase, table=True):
    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "chatwoot_account_id",
            "chatwoot_conversation_id",
            name="uq_chat_message_conversation",
        ),
    )
    id: int | None = Field(default=None, primary_key=True)
    tenant: Tenant | None = Relationship(back_populates="chat_messages")

    def __str__(self) -> str:
        return (
            f"chat_message:{self.id} account:{self.chatwoot_account_id} "
            f"conversation:{self.chatwoot_conversation_id} message:{self.message_id}"
        )


# --- DOCUMENT ---
class Document(SQLModel, table=True):
    __tablename__ = "documents"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: int = Field(foreign_key="tenants.id", ondelete="CASCADE")
    parent_id: UUID | None = Field(
        default=None, foreign_key="documents.id", ondelete="CASCADE"
    )
    filename: str = Field(max_length=255)
    content: str = Field(sa_column=Column(Text, nullable=False))
    metadata_: JSONDict | None = Field(default=None, sa_column=Column(JSONB))
    created_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True))
    )

    tenant: Tenant | None = Relationship(back_populates="documents")

    def __str__(self) -> str:
        return f"document:{self.filename}#{self.id}"
