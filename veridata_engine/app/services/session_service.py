from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.session import BotSession
from app.core.logging import log_start, log_db
import logging

logger = logging.getLogger(__name__)

async def get_or_create_bot_session(
    db: AsyncSession,
    client_id: int,
    conversation_id: str
) -> BotSession:
    """
    Finds an existing BotSession or creates a new one.
    Links the external Chatwoot Conversation ID to our internal tracking.
    """
    session_query = select(BotSession).where(
        BotSession.client_id == client_id,
        BotSession.external_session_id == conversation_id
    )

    sess_result = await db.execute(session_query)
    session = sess_result.scalars().first()

    if not session:
        log_start(logger, f"Creating new BotSession for conversation {conversation_id}")
        session = BotSession(client_id=client_id, external_session_id=conversation_id)
        db.add(session)
        await db.commit()
        await db.refresh(session)
    else:
        log_db(logger, f"Found existing BotSession: {session.id}, RAG ID: {session.rag_session_id}")

    return session
