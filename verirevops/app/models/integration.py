from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class IntegrationConfig(Base):
    __tablename__ = "integration_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    service_name: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # Common fields (nullable as not all services use them)
    url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    api_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    account_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Additional configuration for service-specific fields
    additional_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default={}, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship
    tenant: Mapped["Tenant"] = relationship(back_populates="integrations")
