import asyncio
import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.core.db import AsyncSessionLocal
from app.orquestation.chat import invoke_chat_orchestrator

async def main():
    tenant_id = 2  # Assuming tenant 2 exists
    session_id = 4 # Test session

    # Test 1: ChitChat
    print("\n--- TEST 1: ChitChat ---")
    msg1 = "Hello! Who are you?"
    async with AsyncSessionLocal() as db:
        response1 = await invoke_chat_orchestrator(tenant_id, session_id, msg1, db)
    print(f"User: {msg1}")
    print(f"AI: {response1}")

    # Test 2: RAG
    print("\n--- TEST 2: RAG ---")
    msg2 = "What is the website?"
    async with AsyncSessionLocal() as db:
        response2 = await invoke_chat_orchestrator(tenant_id, session_id, msg2, db)
    print(f"User: {msg2}")
    print(f"AI: {response2}")

if __name__ == "__main__":
    asyncio.run(main())
