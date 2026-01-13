import json
import logging
import uuid

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.integrations.rag import RagClient

logger = logging.getLogger(__name__)

SUMMARY_PROMPT_TEMPLATE = (
    "You are an expert CRM analyst. Analyze the following conversation between a user and an AI assistant.\n"
    "Extract structured information for lead qualification and CRM updates.\n\n"
    "Conversation:\n{history_str}\n\n"
    "Tasks:\n"
    "1. Analyze Purchase Intent (High, Medium, Low, None)\n"
    "2. Assess Urgency (Urgent, Normal, Low)\n"
    "3. Determine Sentiment Score (Positive, Neutral, Negative)\n"
    "4. Detect Budget (if mentioned)\n"
    "5. Extract Contact Info (Name, Phone, Email, Address, Industry)\n"
    "6. Write a concise AI Summary (Markdown)\n"
    "7. Write a Client Description (Professional tone)\n\n"
    "Output must be valid JSON with this structure:\n"
    "{{\n"
    '  "purchase_intent": "...",\n'
    '  "urgency_level": "...",\n'
    '  "sentiment_score": "...",\n'
    '  "detected_budget": null,\n'
    '  "ai_summary": "...",\n'
    '  "contact_info": {{"name": null, "phone": null, "email": null, "address": null, "industry": null}},\n'
    '  "client_description": "..."\n'
    "}}\n\n"
    "JSON Output:"
)


async def summarize_start_conversation(session_id: uuid.UUID, rag_client: RagClient) -> dict:
    """Fetch history from RAG and generate CRM summary using local LLM logic.
    """
    try:
        # 1. Fetch History from RAG
        history_list = await rag_client.get_history(session_id)
        if not history_list:
            logger.warning(f"No history found for session {session_id}")
            return {
                "purchase_intent": "None",
                "urgency_level": "Low",
                "sentiment_score": "Neutral",
                "ai_summary": "No history available.",
                "contact_info": {},
            }

        # Format history
        history_str = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in history_list])

        # 2. Local Summarization with Gemini
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0, google_api_key=settings.google_api_key)

        prompt = SUMMARY_PROMPT_TEMPLATE.format(history_str=history_str)
        messages = [HumanMessage(content=prompt)]

        response = await llm.ainvoke(messages)
        text = response.content.replace("```json", "").replace("```", "").strip()

        try:
            summary_json = json.loads(text)

            # Extract start time from the first message
            start_time = None
            if history_list and "created_at" in history_list[0] and history_list[0]["created_at"]:
                start_time = history_list[0]["created_at"]

            summary_json["session_start_time"] = start_time
            return summary_json

        except json.JSONDecodeError:
            logger.error(f"JSON decode failed for summary: {text}")
            return {
                "purchase_intent": "None",
                "urgency_level": "Low",
                "sentiment_score": "Neutral",
                "ai_summary": "Summarization failed (JSON error).",
                "contact_info": {},
            }

    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        return {
            "purchase_intent": "None",
            "urgency_level": "Low",
            "sentiment_score": "Neutral",
            "ai_summary": f"Error: {str(e)}",
            "contact_info": {},
        }
