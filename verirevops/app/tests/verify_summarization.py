import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select

from app.services.summarization.service import SummarizationService
from app.models import IntegrationConfig, ContactMapping, ChatSession
from app.core.chatwoot import ChatwootClient

async def verify_summarization():
    print("\n🚀 Starting Incremental Summarization Verification...\n")

    # Setup Mock DB
    mock_db = AsyncMock()

    # Mock ChatSession
    mock_session = ChatSession(id=101, tenant_id=1, last_summarized_message_id=100)

    # Mock IntegrationConfigs (HubSpot)
    mock_hs_config = IntegrationConfig(
        id=1, tenant_id=1, service_name="hubspot", is_active=True,
        url="https://api.hubapi.com", api_key="hs_key"
    )

    async def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        if "chat_sessions" in stmt_str:
            mock_res = MagicMock()
            mock_res.scalars().first.return_value = mock_session
            return mock_res
        if "integration_configs" in stmt_str:
            mock_res = MagicMock()
            mock_res.scalars().all.return_value = [mock_hs_config]
            return mock_res
        if "contact_mappings" in stmt_str and "hubspot" in stmt_str:
            # Check if it's searching for the actual contact_id (500)
            # instead of the conversation_id (101)
            if "500" in stmt_str:
                mock_res = MagicMock()
                mock_res.scalars().first.return_value = "HS_ID_123"
                return mock_res
            else:
                # If it searches for 101, return nothing (fails the test)
                return MagicMock()
        return MagicMock()

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    # Setup Mock Chatwoot Client
    mock_client = AsyncMock(spec=ChatwootClient)

    # Define simple message list
    messages = [
        {"id": 101, "sender": {"name": "User"}, "content": "Help me!"},
        {"id": 102, "sender": {"name": "Agent"}, "content": "Sure, I'm here."}
    ]

    async def mock_get_messages(account_id, conversation_id, after=None):
        if after is not None:
            return [m for m in messages if m["id"] > after]
        return messages

    mock_client.get_messages = AsyncMock(side_effect=mock_get_messages)
    mock_client.get_conversation = AsyncMock(return_value={"id": 101, "contact_id": 500})

    # Patch adapters and LLM
    with patch("app.services.crm.factory.CRMFactory.get_adapter") as mock_get_adapter, \
         patch("app.services.summarization.service.SummarizationService._generate_summary", new_callable=AsyncMock) as mock_gen:

        mock_hs_adapter = AsyncMock()
        mock_get_adapter.return_value = mock_hs_adapter
        mock_gen.return_value = "AI summary content"

        service = SummarizationService(mock_db, mock_client)

        print("🔹 Scenario 1: Incremental Summary (Detected new messages)")
        # Session has last_id = 100. Messages 101, 102 are new.
        await service.summarize_conversation(1, 1, 101, send_to_crm=False, cleanup_history=False)

        assert mock_client.get_messages.called, "Should call get_messages"
        assert mock_client.send_message.called, "Should send private note to Chatwoot"
        assert mock_session.last_summarized_message_id == 102, "Should update last_summarized_message_id to 102"
        print("✅ Scenario 1 Passed")

        print("\n🔹 Scenario 2: No new messages (Skip summary)")
        mock_client.send_message.reset_mock()
        # mock_session now has 102.
        await service.summarize_conversation(1, 1, 101, send_to_crm=False, cleanup_history=False)

        assert not mock_client.send_message.called, "Should NOT send summary if no new messages"
        print("✅ Scenario 2 Passed")

        print("\n🔹 Scenario 3: Final Resolution (CRM Sync + Cleanup)")
        mock_hs_adapter.add_note.reset_mock()
        # Reset session to test resolution
        mock_session.last_summarized_message_id = 100
        await service.summarize_conversation(1, 1, 101, send_to_crm=True, cleanup_history=True)

        assert mock_hs_adapter.add_note.called, "Should sync to CRM"
        print("✅ Scenario 3 Passed")

    print("\n✨ Incremental Summarization Verification complete!\n")

if __name__ == "__main__":
    asyncio.run(verify_summarization())
