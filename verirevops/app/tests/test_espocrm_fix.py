import asyncio
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.services.crm.adapters.espocrm import EspoCRMAdapter

async def test_espocrm_search_fix():
    print("\n--- Testing EspoCRM Search Fix ---")

    adapter = EspoCRMAdapter(url="https://espo.example.com", api_key="test-key")
    email = "test@example.com"

    # Mock httpx.AsyncClient.get
    with patch("httpx.AsyncClient.get") as mock_get:
        # 1. Test successful search with matching results
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "list": [{"id": "espo-123", "firstName": "Test", "emailAddress": "test@example.com"}],
            "total": 1
        }
        mock_get.return_value = mock_response

        result = await adapter.find_contact_by_email(email)

        args, kwargs = mock_get.call_args
        params = kwargs.get("params", {})

        print(f"Sent params: {params}")

        # Verify correct JSON params
        import json
        where = json.loads(params.get("where"))
        assert where[0]["type"] == "equals"
        assert where[0]["attribute"] == "emailAddress"
        assert where[0]["value"] == email

        print(f"Result: {result}")
        assert result["id"] == "espo-123"
        assert result["emailAddress"] == "test@example.com"
        print("✅ Success: Correct JSON parameters sent and result validated.")

        # 2. Test search with NON-matching result (Simulating API ignoring filter)
        mock_response.json.return_value = {
            "list": [{"id": "other-id", "emailAddress": "wrong@example.com"}],
            "total": 5
        }
        result = await adapter.find_contact_by_email(email)
        assert result is None
        print("✅ Success: Non-matching email correctly rejected (Identity collision prevented).")

        # 3. Test search with NO results
        mock_response.json.return_value = {"list": [], "total": 0}
        result = await adapter.find_contact_by_email("unknown@example.com")
        assert result is None
        print("✅ Success: Empty results correctly return None.")

if __name__ == "__main__":
    asyncio.run(test_espocrm_search_fix())
