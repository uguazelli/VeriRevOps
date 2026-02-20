from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from app.core.config import settings
from app.core.logger import Log
from app.orchestration.state import ChatState

async def transcribe_node(state: ChatState, config: RunnableConfig) -> dict:
    """
    If the user message is empty but there are attachments, use Gemini to
    transcribe/describe the media into the 'user_message' field.
    If text exists, append the transcription/description.
    """
    if not state.get('attachments'):
        return {} # Nothing to transcribe

    # Detect media types to build a dynamic prompt
    audio_count = sum(1 for att in state['attachments'] if att.get("type") == "audio")
    image_count = sum(1 for att in state['attachments'] if att.get("type") == "image")

    if audio_count == 0 and image_count == 0:
        return {}

    Log.orchestrator(f"Processing media: {audio_count} audio, {image_count} images.")

    llm = ChatGoogleGenerativeAI(model=settings.MODEL, temperature=0, google_api_key=settings.GOOGLE_API_KEY)

    # Multi-part content for Gemini - Build prompt dynamically
    instructions = []
    if audio_count > 0:
        instructions.append("Audio: Transcribe strictly what is said.")
    if image_count > 0:
        instructions.append("Image: Describe what is shown in detail.")

    prompt_text = (
        "Focus only on the provided media. "
        + " ".join(instructions)
        + " Return ONLY the transcription/description. Do not add preamble."
    )
    human_content = [{"type": "text", "text": prompt_text}]

    for att in state['attachments']:
        if att.get("type") in ["image", "audio"]:
            human_content.append({
                "type": "media",
                "mime_type": att.get("mime_type"),
                "data": att.get("data")
            })

    response = await llm.ainvoke([HumanMessage(content=human_content)], config=config)
    transcription = response.content.strip()

    Log.orchestrator(f"Transcription/Description result: '{transcription}'")

    current_text = state.get('user_message', "")
    if current_text:
        new_text = f"{current_text}\n\n[Media Content]: {transcription}"
    else:
        new_text = transcription

    return {"user_message": new_text}
