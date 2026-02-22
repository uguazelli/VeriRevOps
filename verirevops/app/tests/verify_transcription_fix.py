import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.orchestration.nodes.transcribe import transcribe_node
from app.core.logger import Log

async def verify_transcribe_node():
    print("🚀 Verifying transcribe_node with dynamic prompts...")

    # Mock LLM response
    mock_response = MagicMock()
    mock_response.content = "This is a mock transcription/description."

    # Mock ChatGoogleGenerativeAI
    import app.orchestration.nodes.transcribe as transcribe_mod
    transcribe_mod.ChatGoogleGenerativeAI = MagicMock()

    mock_llm_instance = MagicMock()
    mock_llm_instance.ainvoke = AsyncMock(return_value=mock_response)
    transcribe_mod.ChatGoogleGenerativeAI.return_value = mock_llm_instance

    config = {"configurable": {"db": MagicMock()}}

    # Case 1: Audio only
    print("\n--- Test Case 1: Audio Only ---")
    state_audio = {
        "attachments": [{"type": "audio", "mime_type": "audio/mpeg", "data": "base64audio"}],
        "user_message": ""
    }
    await transcribe_node(state_audio, config)

    # Check prompt text in call
    call_args = mock_llm_instance.ainvoke.call_args[0][0][0]
    prompt_text = call_args.content[0]["text"]
    print(f"Prompt used: {prompt_text}")
    assert "Audio:" in prompt_text
    assert "Image:" not in prompt_text
    print("✅ Result: Prompt correctly contains Audio and NOT Image.")

    # Case 2: Image only
    print("\n--- Test Case 2: Image Only ---")
    mock_llm_instance.ainvoke.reset_mock()
    state_image = {
        "attachments": [{"type": "image", "mime_type": "image/jpeg", "data": "base64image"}],
        "user_message": ""
    }
    await transcribe_node(state_image, config)

    call_args = mock_llm_instance.ainvoke.call_args[0][0][0]
    prompt_text = call_args.content[0]["text"]
    print(f"Prompt used: {prompt_text}")
    assert "Image:" in prompt_text
    assert "Audio:" not in prompt_text
    print("✅ Result: Prompt correctly contains Image and NOT Audio.")

    # Case 3: Both
    print("\n--- Test Case 3: Both Audio and Image ---")
    mock_llm_instance.ainvoke.reset_mock()
    state_both = {
        "attachments": [
            {"type": "audio", "mime_type": "audio/mpeg", "data": "base64audio"},
            {"type": "image", "mime_type": "image/jpeg", "data": "base64image"}
        ],
        "user_message": ""
    }
    await transcribe_node(state_both, config)

    call_args = mock_llm_instance.ainvoke.call_args[0][0][0]
    prompt_text = call_args.content[0]["text"]
    print(f"Prompt used: {prompt_text}")
    assert "Image:" in prompt_text
    assert "Audio:" in prompt_text
    print("✅ Result: Prompt correctly contains both.")

    # Case 4: No media (unsupported type)
    print("\n--- Test Case 4: No supported media ---")
    mock_llm_instance.ainvoke.reset_mock()
    state_none = {
        "attachments": [{"type": "file", "mime_type": "application/pdf", "data": "base64"}],
        "user_message": "test"
    }
    result = await transcribe_node(state_none, config)
    assert result == {}
    assert not mock_llm_instance.ainvoke.called
    print("✅ Result: Correctly skipped for unsupported media types.")

    print("\n🎉 All verification cases passed!")

if __name__ == "__main__":
    asyncio.run(verify_transcribe_node())
