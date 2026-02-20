import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.services.summarization.service import SummarizationService

async def test_refactored_summarization():
    print("\n--- Testing Refactored Summarization Service ---")

    # 1. Setup Mock DB and Client
    db = AsyncMock()
    client = AsyncMock()
    service = SummarizationService(db, client)

    # Mock summarize_conversation to just check if it's called with right params
    service.summarize_conversation = AsyncMock()

    # Mock DB query for account_id fallback
    result_config = MagicMock()
    result_config.scalars().first.return_value = "123"
    db.execute.return_value = result_config

    # Sample webhook data (minimal)
    data = {
        "status": "resolved",
        "id": 456,
        "account": {"id": 123},
        "conversation": {
            "contact_id": 789,
            "last_message": {"id": 1000}
        }
    }

    print("Testing process_webhook_status_change with full data...")
    await service.process_webhook_status_change(data, 1)

    service.summarize_conversation.assert_called_with(
        1, 123, 456, status="resolved", contact_id=789, latest_message_id=1000
    )
    print("✅ Success: parameters correctly extracted and passed.")

    # Test fallback to DB for account_id
    data_no_account = {
        "status": "resolved",
        "id": 456,
        "conversation": {"id": 456}
    }

    service.summarize_conversation.reset_mock()
    print("Testing account_id fallback to DB...")
    await service.process_webhook_status_change(data_no_account, 1)

    service.summarize_conversation.assert_called_with(
        1, 123, 456, status="resolved", contact_id=None, latest_message_id=None
    )
    print("✅ Success: account_id fallback works.")

    print("\nRefactoring verification complete!")

if __name__ == "__main__":
    asyncio.run(test_refactored_summarization())
