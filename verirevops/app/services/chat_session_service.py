from datetime import datetime
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.chat import ChatSession
from app.schemas.chat import SessionKey
from app.core.logger import Log

class ChatSessionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def update_session_activity(self, key: SessionKey, status: str):
        """Updates the last_activity_at and status for a chat session."""
        stmt = (
            update(ChatSession)
            .where(
                ChatSession.tenant_id == key.tenant_id,
                ChatSession.chatwoot_account_id == key.account_id,
                ChatSession.chatwoot_conversation_id == key.conversation_id
            )
            .values(
                last_activity_at=datetime.utcnow(),
                status=status
            )
        )
        result = await self.db.execute(stmt)
        if result.rowcount == 0:
            new_session = ChatSession(
                id=key.conversation_id,
                tenant_id=key.tenant_id,
                chatwoot_account_id=key.account_id,
                chatwoot_conversation_id=key.conversation_id,
                status=status,
                last_activity_at=datetime.utcnow()
            )
            self.db.add(new_session)

        await self.db.commit()
        Log.info(f"Updated activity for session {key.conversation_id} (Status: {status})")

    async def update_tracking_id(self, key: SessionKey, tracking_id: int, status: str):
        """Updates the last_summarized_message_id for a session."""
        session = await self.get_session(key)

        if session:
            session.last_summarized_message_id = tracking_id
            session.status = status
            session.last_activity_at = datetime.utcnow()
            Log.info(f"Updated session {key.conversation_id} tracking to message {tracking_id}")
        else:
            new_session = ChatSession(
                id=key.conversation_id,
                tenant_id=key.tenant_id,
                chatwoot_account_id=key.account_id,
                chatwoot_conversation_id=key.conversation_id,
                last_summarized_message_id=tracking_id,
                status=status,
                last_activity_at=datetime.utcnow()
            )
            self.db.add(new_session)
            Log.info(f"Created new session {key.conversation_id} with tracking message {tracking_id}")

        await self.db.commit()

    async def ensure_session(self, key: SessionKey) -> Optional[ChatSession]:
        """Ensures a session exists, creating it if necessary."""
        session = await self.get_session(key)
        if session:
            return session

        Log.info(f"Creating missing session {key.conversation_id}")
        new_session = ChatSession(
            id=key.conversation_id,
            tenant_id=key.tenant_id,
            chatwoot_account_id=key.account_id,
            chatwoot_conversation_id=key.conversation_id,
            status="pending",
            last_activity_at=datetime.utcnow()
        )
        self.db.add(new_session)
        await self.db.commit()
        return new_session

    async def get_session(self, key: SessionKey) -> Optional[ChatSession]:
        """Fetches a chat session."""
        stmt = select(ChatSession).where(
            ChatSession.tenant_id == key.tenant_id,
            ChatSession.chatwoot_account_id == key.account_id,
            ChatSession.chatwoot_conversation_id == key.conversation_id
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
