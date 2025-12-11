import asyncio
import sys
import os
from unittest.mock import AsyncMock, patch

# Ensure logic is importable
sys.path.append(os.getcwd())

from app.services import bot_service
from app.controller import evolution, telegram

async def test_evolution_flow():
    print("\n🧪 Testing Evolution Webhook Flow...")

    # Mock Payload
    payload = {
        "event": "messages.upsert",
        "instance": "test_instance",
        "data": {
            "key": {"remoteJid": "5511999999999@s.whatsapp.net", "fromMe": False},
            "message": {"conversation": "Hello Bot"}
        }
    }

    # Mock Deps
    with patch("app.services.bot_service.database") as mock_db, \
         patch("app.services.bot_service.rag_service") as mock_rag, \
         patch("app.controller.evolution.message_whatsapp") as mock_send:

        # Configure AsyncMocks
        mock_db.get_session_status = AsyncMock(return_value=True)
        mock_db.get_tenant_id = AsyncMock(return_value="tenant_123")
        mock_db.get_session_id = AsyncMock(return_value="sess_1")
        mock_db.update_session_id = AsyncMock()
        mock_db.set_session_active = AsyncMock()

        mock_rag.query_rag = AsyncMock(return_value={"text": "Hello Human"})

        # message_whatsapp in evolution is imported, so patch mocks the *imported name*.
        # patch creates a MagicMock by default.
        mock_send.return_value = None

        res = await evolution.process_webhook(payload)

        print(f"Result: {res}")

        # Verify RAG was called
        mock_rag.query_rag.assert_called_with(tenant_id="tenant_123", query="Hello Bot", session_id="sess_1")

        # Verify Reply was sent (via callback)
        mock_send.assert_called_with(instance="test_instance", phone="5511999999999", message="Hello Human")
        print("✅ Evolution Flow Failed" if not mock_send.called else "✅ Evolution Flow Passed")

async def test_telegram_flow():
    print("\n🧪 Testing Telegram Webhook Flow...")

    token = "123456:ABC-DEF"
    payload = {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "chat": {"id": 987654321},
            "text": "Hello Telegram"
        }
    }

    with patch("app.services.bot_service.database") as mock_db, \
         patch("app.services.bot_service.rag_service") as mock_rag, \
         patch("app.controller.telegram.send_message") as mock_send:

        mock_db.get_session_status = AsyncMock(return_value=True)
        mock_db.get_tenant_id = AsyncMock(return_value="tenant_456")
        mock_db.get_session_id = AsyncMock(return_value="sess_2")
        mock_db.update_session_id = AsyncMock()

        mock_rag.query_rag = AsyncMock(return_value={"text": "Hello User"})

        # Make send_message awaitable
        mock_send.return_value = None

        # Call controller
        res = await telegram.process_webhook(token, payload)

        print(f"Result: {res}")

        # Verify RAG call
        mock_rag.query_rag.assert_called_with(tenant_id="tenant_456", query="Hello Telegram", session_id="sess_2")

        # Verify Send Message
        mock_send.assert_called_with(token, "987654321", "Hello User")
        print("✅ Telegram Flow Passed" if mock_send.called else "❌ Telegram Flow Failed")

if __name__ == "__main__":
    asyncio.run(test_evolution_flow())
    asyncio.run(test_telegram_flow())
