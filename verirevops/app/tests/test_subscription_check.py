import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.services.chatbot_service import ChatbotService
from app.models import Subscription, Tenant

async def test_subscription_logic():
    print("\n--- Testing Subscription Logic ---")

    # 1. Setup Mock DB and Tenant
    db = AsyncMock()
    tenant = MagicMock()
    tenant.id = 1

    # Mock _resolve_tenant
    service = ChatbotService(db)
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

    async def run_test_case(case_name, sub_obj, expected_called):
        print(f"Testing {case_name}...")

        # Reset mocks
        service._send_ai_response.reset_mock()
        db.execute.reset_mock()

        # Mock Subscription query result
        result = MagicMock()
        result.scalars().first.return_value = sub_obj
        db.execute.return_value = result

        await service.process_webhook_message(data, "test-alias")

        if expected_called:
            service._send_ai_response.assert_called()
            print(f"✅ {case_name}: Processed successfully.")
        else:
            service._send_ai_response.assert_not_called()
            print(f"✅ {case_name}: Correctly skipped.")

    # --- TEST CASES ---

    # Case 1: Valid Subscription
    valid_sub = Subscription(id=1, tenant_id=1, quota_limit=100, usage_count=50, end_date=datetime.now() + timedelta(days=10))
    await run_test_case("Valid Subscription", valid_sub, True)

    # Case 2: No Subscription
    await run_test_case("No Subscription", None, False)

    # Case 3: Quota Exceeded
    over_quota_sub = Subscription(id=2, tenant_id=1, quota_limit=10, usage_count=10, end_date=datetime.now() + timedelta(days=10))
    await run_test_case("Quota Exceeded", over_quota_sub, False)

    # Case 4: Expired Subscription
    expired_sub = Subscription(id=3, tenant_id=1, quota_limit=100, usage_count=0, end_date=datetime.now() - timedelta(days=1))
    await run_test_case("Expired Subscription", expired_sub, False)

    print("\nAll subscription test cases passed!")

if __name__ == "__main__":
    asyncio.run(test_subscription_logic())
