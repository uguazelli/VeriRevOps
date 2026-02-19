from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class ChatwootConfig(Base):
    __tablename__ = "chatwoot_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), unique=True, nullable=False)
    api_url: Mapped[str] = mapped_column(String, nullable=False)
    api_access_token: Mapped[str] = mapped_column(String, nullable=False)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    tenant: Mapped["Tenant"] = relationship(back_populates="chatwoot_config")
