import json
import os
import logging
from typing import Any, Dict
from src.storage.db import get_db

logger = logging.getLogger(__name__)

_config_cache = None

def get_config(force_reload: bool = False) -> Dict[str, Any]:
    global _config_cache
    if _config_cache is not None and not force_reload:
        return _config_cache

    config = {}
    # Load from JSON
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config.update(json.load(f))
        except Exception as e:
            logger.error(f"Failed to load config.json: {e}")

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT config FROM global_configs ORDER BY id DESC LIMIT 1")
                row = cur.fetchone()
                if row:
                    db_config = row[0]
                    if isinstance(db_config, dict):
                        config.update(db_config)
                        logger.info("Loaded global config from database")
    except Exception as e:
        logger.warning(f"Could not load config from DB (table might not exist yet): {e}")

    _config_cache = config
    return _config_cache

def get_llm_settings(step: str) -> Dict[str, str]:
    config = get_config()
    llm_config = config.get("llm_config", {})
    steps = llm_config.get("steps", {})

    step_config = steps.get(step, steps.get("generation", {
        "provider": "gemini",
        "model": "models/gemini-2.0-flash"
    }))

    return step_config

def get_global_setting(key: str, default: Any = None) -> Any:
    config = get_config()
    llm_config = config.get("llm_config", {})
    return llm_config.get(key, default)
