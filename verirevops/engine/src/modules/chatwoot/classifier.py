import json
import logging

from src.core.json_utils import parse_json_object
from src.core.prompts import CHATWOOT_TRAFFIC_CLASSIFIER_PROMPT
from src.modules.ai.text import get_chat_response
from src.modules.chatwoot.payload import normalize_chatwoot_history


logger = logging.getLogger(__name__)

VALID_CHATWOOT_CATEGORIES = {"RETRIEVAL", "CHITCHAT", "HANDOFF", "OUT_OF_SCOPE"}
MIN_CHATWOOT_CLASSIFICATION_CONFIDENCE = 0.75


def build_chatwoot_classification_prompt(message_history, current_message):
    normalized_history = normalize_chatwoot_history(message_history)
    history_json = json.dumps(normalized_history, indent=2, default=str)
    current_message_text = current_message.strip() if current_message else "EMPTY_QUERY"

    return CHATWOOT_TRAFFIC_CLASSIFIER_PROMPT.format(
        message_history=history_json,
        current_message=current_message_text
    )


def parse_chatwoot_classification(raw_response):
    return parse_json_object(
        raw_response,
        fallback=build_default_chatwoot_classification,
        logger=logger,
        error_message="Failed to parse Chatwoot classification JSON",
    )


def build_default_chatwoot_classification():
    return {
        "data": {
            "category": "HANDOFF",
            "confidence": 0.0,
            "allowed_to_answer": False,
            "handoff_required": True,
            "reason": "classifier returned invalid JSON",
        }
    }


def get_classification_category(classification):
    data = get_classification_data(classification)

    if classification_requires_handoff(classification):
        return "HANDOFF"

    category = data.get("category")

    if isinstance(category, str):
        normalized_category = category.upper()
        if normalized_category in VALID_CHATWOOT_CATEGORIES:
            return normalized_category

    return "HANDOFF"


def get_classification_data(classification):
    if not isinstance(classification, dict):
        return {}

    data = classification.get("data")
    if not isinstance(data, dict):
        return {}

    return data


def classification_requires_handoff(classification):
    data = get_classification_data(classification)

    category = data.get("category")
    normalized_category = category.upper() if isinstance(category, str) else "HANDOFF"

    if normalized_category not in VALID_CHATWOOT_CATEGORIES:
        return True

    if normalized_category == "HANDOFF":
        return True

    if normalized_category == "OUT_OF_SCOPE":
        return True

    if get_classification_confidence(data) < MIN_CHATWOOT_CLASSIFICATION_CONFIDENCE:
        return True

    if data.get("allowed_to_answer") is not True:
        return True

    if data.get("handoff_required") is True:
        return True

    return False


def get_classification_confidence(data):
    try:
        return float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        return 0.0


async def classify_chatwoot_message(message_history, current_message, provider: str = "gemini"):
    prompt = build_chatwoot_classification_prompt(message_history, current_message)
    raw_response = await get_chat_response(prompt, provider=provider)
    classification = parse_chatwoot_classification(raw_response)
    logger.info("☎️ Chatwoot message classification: %s", classification)
    return classification
