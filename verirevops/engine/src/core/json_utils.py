import json
import logging
from collections.abc import Callable
from typing import Any


def parse_json_object(
    raw_text: str,
    *,
    fallback: Callable[[], dict[str, Any]],
    logger: logging.Logger | None = None,
    error_message: str = "Failed to parse JSON object",
) -> dict[str, Any]:
    response_text = raw_text.strip() if isinstance(raw_text, str) else ""
    parsed = _loads_json_object(response_text)

    if parsed is not None:
        return parsed

    if logger:
        logger.error("%s: %s", error_message, raw_text)

    return fallback()


def _loads_json_object(response_text: str) -> dict[str, Any] | None:
    if not response_text:
        return None

    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        parsed = _loads_embedded_json_object(response_text)

    if isinstance(parsed, dict):
        return parsed

    return None


def _loads_embedded_json_object(response_text: str) -> Any:
    start = response_text.find("{")
    end = response_text.rfind("}")

    if start == -1 or end == -1 or start >= end:
        return None

    try:
        return json.loads(response_text[start : end + 1])
    except json.JSONDecodeError:
        return None
