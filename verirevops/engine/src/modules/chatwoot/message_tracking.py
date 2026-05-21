from sqlmodel import select

from src.core.db import get_session
from src.core.models import ChatMessage
from src.modules.chatwoot.schemas import ChatMessageCreate


async def svc_upsert_chat_message(
    message_data: ChatMessageCreate,
) -> ChatMessage:
    async with get_session() as db:
        query = select(ChatMessage).where(
            ChatMessage.tenant_id == message_data.tenant_id,
            ChatMessage.chatwoot_account_id == message_data.chatwoot_account_id,
            ChatMessage.chatwoot_conversation_id == message_data.chatwoot_conversation_id,
        )
        result = await db.execute(query)
        chat_message = result.scalar_one_or_none()

        if chat_message:
            chat_message.message_id = message_data.message_id
        else:
            chat_message = ChatMessage(**message_data.model_dump())
            db.add(chat_message)

        await db.commit()
        await db.refresh(chat_message)
        return chat_message


async def svc_list_chat_messages(
    tenant_id: int | None = None,
    chatwoot_account_id: int | None = None,
    chatwoot_conversation_id: int | None = None,
) -> list[ChatMessage]:
    async with get_session() as db:
        query = select(ChatMessage)
        if tenant_id:
            query = query.where(ChatMessage.tenant_id == tenant_id)
        if chatwoot_account_id:
            query = query.where(ChatMessage.chatwoot_account_id == chatwoot_account_id)
        if chatwoot_conversation_id:
            query = query.where(
                ChatMessage.chatwoot_conversation_id == chatwoot_conversation_id
            )

        result = await db.execute(query)
        return result.scalars().all()
