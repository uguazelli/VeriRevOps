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

    Log.orchestrator("Processing media for transcription/description...")

    llm = ChatGoogleGenerativeAI(model=settings.MODEL, temperature=0, google_api_key=settings.GOOGLE_API_KEY)

    # Multi-part content for Gemini
    prompt_text = (
        "Focus only on the provided media. "
        "Audio: Transcribe strictly what is said. "
        "Image: Describe what is shown in detail. "
        "Return ONLY the transcription/description. Do not add preamble."
    )
    human_content = [{"type": "text", "text": prompt_text}]

    has_media = False
    for att in state['attachments']:
        if att.get("type") in ["image", "audio"]:
            human_content.append({
                "type": "media",
                "mime_type": att.get("mime_type"),
                "data": att.get("data")
            })
            has_media = True

    if not has_media:
        return {}

    response = await llm.ainvoke([HumanMessage(content=human_content)], config=config)
    transcription = response.content.strip()

    Log.orchestrator(f"Transcription/Description results: '{transcription}'")

    current_text = state.get('user_message', "")
    if current_text:
        new_text = f"{current_text}\n\n[Media Content]: {transcription}"
    else:
        new_text = transcription

    return {"user_message": new_text}
