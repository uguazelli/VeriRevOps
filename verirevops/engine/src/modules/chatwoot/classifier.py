import json
import logging

from src.core.prompts import CHATWOOT_TRAFFIC_CLASSIFIER_PROMPT
from src.modules.chatwoot.payload import normalize_chatwoot_history
from src.services.llm import get_chat_response


logger = logging.getLogger(__name__)


def build_chatwoot_classification_prompt(message_history, current_message):
    normalized_history = normalize_chatwoot_history(message_history)
    history_json = json.dumps(normalized_history, indent=2, default=str)
    current_message_text = current_message.strip() if current_message else "EMPTY_QUERY"

    return CHATWOOT_TRAFFIC_CLASSIFIER_PROMPT.format(
        message_history=history_json,
        current_message=current_message_text
    )


def parse_chatwoot_classification(raw_response):
    response_text = raw_response.strip()

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        start = response_text.find("{")
        end = response_text.rfind("}")

    if start != -1 and end != -1 and start < end:
        try:
            return json.loads(response_text[start:end + 1])
        except json.JSONDecodeError:
            pass

    logger.error("Failed to parse Chatwoot classification JSON: %s", raw_response)
    return {
        "data": {
            "category": "HANDOFF",
            "confidence": 0.0,
            "reason": "classifier returned invalid JSON"
        }
    }


def get_classification_category(classification):
    if not isinstance(classification, dict):
        return "HANDOFF"

    category = classification.get("data", {}).get("category")

    if isinstance(category, str):
        normalized_category = category.upper()
        if normalized_category in {"RETRIEVAL", "CHITCHAT", "HANDOFF"}:
            return normalized_category

    return "HANDOFF"


async def classify_chatwoot_message(message_history, current_message, provider: str = "gemini"):
    prompt = build_chatwoot_classification_prompt(message_history, current_message)
    raw_response = await get_chat_response(prompt, provider=provider)
    classification = parse_chatwoot_classification(raw_response)
    logger.info("☎️ Chatwoot message classification: %s", classification)
    return classification
