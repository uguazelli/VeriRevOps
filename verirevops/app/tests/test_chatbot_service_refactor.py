import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.services.chatbot_service import ChatbotService

async def test_refactor():
    print("Testing refactored ChatbotService...")

    # Mock DB
    db = MagicMock()
    db.execute = AsyncMock()

    # Mock Tenant
    tenant = MagicMock()
    tenant.id = 1

    # Mock execute result
    result = MagicMock()
    result.scalars().first.return_value = tenant
    db.execute.return_value = result

    service = ChatbotService(db)

    # Mock private methods to test flow
    service._resolve_tenant = AsyncMock(return_value=tenant)
    service._resolve_client = AsyncMock()
    service._process_attachments = AsyncMock(return_value=[])
    service._send_ai_response = AsyncMock()

    # Mock orchestrator
    import app.services.chatbot_service as cs
    cs.invoke_chat_orchestrator = AsyncMock(return_value=("Hi", "chitchat"))

    data = {
        "account": {"id": 1},
        "conversation": {"id": 1, "status": "pending"},
        "content": "Hello",
        "attachments": []
    }

    await service.process_webhook_message(data, "test-alias")

    print("Verification complete! The flow reached the end successfully.")

if __name__ == "__main__":
    asyncio.run(test_refactor())
