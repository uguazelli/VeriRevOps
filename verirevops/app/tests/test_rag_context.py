import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import HumanMessage, AIMessage

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.rag.retrieve import invoke_rag_graph

async def test_rag_context_awareness():
    print("\n--- Testing RAG Context Awareness (Name Recognition) ---")

    # 1. Setup Mock DB
    db = AsyncMock()

    # 2. Mock History (where the user says their name)
    chat_history = [
        HumanMessage(content="hi"),
        AIMessage(content="Hello! How can I help you today?"),
        HumanMessage(content="my name is ugo"),
        AIMessage(content="It's a pleasure to meet you, Ugo! How can I help you today at VeriRevOps?")
    ]

    # 3. User query that triggers RAG but requires history for name
    user_query = "do you know my name?"

    # 4. Mock Retrieval results (no mention of user name, just company info)
    # We need to mock _fetch_top_chunks in app.rag.retrieve
    import app.rag.retrieve as rr

    # Mocking the embedding to avoid real API calls
    rr._get_embedding_with_retry = AsyncMock(return_value=[0.1] * 3072)

    # Mocking chunk retrieval
    mock_chunk = MagicMock()
    mock_chunk.id = 1
    mock_chunk.content = "Veridata Pro is a RevOps agency founded by Ugo Guazelli. Our website is www.veridatapro.com."
    mock_chunk.chunk_metadata = {}
    rr._fetch_top_chunks = AsyncMock(return_value=[mock_chunk])

    print(f"Query: {user_query}")
    print(f"History contains: 'my name is ugo'")

    # Execute RAG
    answer = await invoke_rag_graph(
        session_id=5,
        user_query=user_query,
        db_session=db,
        tenant_id=2,
        account_id=1,
        chat_history=chat_history
    )

    print(f"\nAI Response: {answer}")

    if "ugo" in answer.lower():
        print("\n✅ Success: AI recognized the user's name from history during RAG!")
    else:
        print("\n❌ Failure: AI still doesn't recognize the user's name.")

if __name__ == "__main__":
    asyncio.run(test_rag_context_awareness())
