import asyncio
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.models.tenant import Tenant
from app.services.tenant.service import TenantService
from app.orchestration.nodes.ingest import load_and_ensure_session
from app.orchestration.state import ChatState
from langchain_core.runnables import RunnableConfig

@pytest.mark.async_timeout(30)
@pytest.mark.asyncio
async def test_custom_prompt_loading():
    # 1. Setup DB session
    async for session in get_db():
        # 2. Create a test tenant with a custom prompt
        tenant_service = TenantService(session)
        tenant_id = 9999

        # Ensure clean state
        existing = await session.get(Tenant, tenant_id)
        if existing:
            await session.delete(existing)
            await session.commit()

        test_prompt = "You are a very friendly assistant. If someone asks for prices, say 'Please contact human'."
        tenant = Tenant(
            id=tenant_id,
            name="Test Tenant",
            slug="test-tenant-prompt",
            url="http://test.com",
            custom_prompt=test_prompt
        )
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)

        # 3. Test ingest node loading
        state = ChatState(
            tenant_id=tenant_id,
            account_id=1,
            session_id=1,
            user_message="Hello",
            chat_history=[],
            intent="chitchat",
            ai_response="",
            summary_needed=False,
            attachments=[]
        )

        config = RunnableConfig(configurable={"db": session, "chatwoot_client": None})

        result = await load_and_ensure_session(state, config)

        assert "custom_prompt" in result
        assert result["custom_prompt"] == test_prompt

        # Cleanup
        await session.delete(tenant)
        await session.commit()
        break

if __name__ == "__main__":
    asyncio.run(test_custom_prompt_loading())
