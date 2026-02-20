from datetime import datetime
from typing import List, Optional
from sqlalchemy import Integer, String, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    chatwoot_conversation_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)
    chatwoot_account_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_summarized_message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="chat_sessions")
