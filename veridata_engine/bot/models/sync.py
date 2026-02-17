from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, TIMESTAMP, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.models.base import Base


class SyncConfig(Base):
    __tablename__ = "sync_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    platform: Mapped[str] = mapped_column(String, index=True)
    config_json: Mapped[dict] = mapped_column(JSON, default={})
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    frequency_minutes: Mapped[int] = mapped_column(Integer, default=60)
    inactivity_threshold_minutes: Mapped[Optional[int]] = mapped_column(Integer, default=30)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    client: Mapped["Client"] = relationship("Client", back_populates="sync_configs")

    def __str__(self):
        return f"{self.platform} ({self.frequency_minutes}m)"
