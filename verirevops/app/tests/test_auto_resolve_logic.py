import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta
from sqlalchemy import select
from app.models.chat import ChatSession
from app.scripts.auto_resolve import resolve_idle_conversations
from app.core.db import AsyncSessionLocal

@pytest.mark.asyncio
async def test_resolve_idle_conversations_logic():
    """
    Verifies that the auto-resolve job correctly identifies idle sessions
    without actually connecting to a real database.
    """
    # 1. Mock DB Session and its methods
    mock_db = AsyncMock()

    # Mock the return value of the query
    idle_time = datetime.utcnow() - timedelta(hours=2)
    mock_session = ChatSession(
        id=999,
        tenant_id=1,
        chatwoot_account_id=1,
        chatwoot_conversation_id=999,
        status="open",
        last_activity_at=idle_time
    )

    # Mock the result of the execute() call
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_session]
    mock_db.execute.return_value = mock_result

    # 2. Mock ChatwootClient
    mock_client = AsyncMock()
    mock_client.update_status = AsyncMock(return_value={"status": "success"})

    # 3. Patch everything
    with patch("app.scripts.auto_resolve._resolve_client", return_value=mock_client):
        # Patch AsyncSessionLocal as a context manager
        mock_db_context = AsyncMock()
        mock_db_context.__aenter__.return_value = mock_db

        with patch("app.scripts.auto_resolve.AsyncSessionLocal", return_value=mock_db_context):
            # 4. Run the job
            await resolve_idle_conversations()

    # 5. Verify query was called correctly
    mock_db.execute.assert_called()

    # 6. Verify Chatwoot was called
    mock_client.update_status.assert_called_once_with(1, 999, "resolved")
