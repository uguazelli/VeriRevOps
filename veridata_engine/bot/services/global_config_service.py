from sqlalchemy import select
from bot.core.db import async_session_maker
from bot.models.config import GlobalConfig

async def get_llm_config() -> dict:
    """
    Fetches the LLM configuration from the GlobalConfig table.
    Raises ValueError if configuration is missing or invalid.
    """
    async with async_session_maker() as session:
        result = await session.execute(select(GlobalConfig).order_by(GlobalConfig.updated_at.desc()).limit(1))
        config = result.scalars().first()

        if not config:
            raise ValueError("GlobalConfig not found in database. Please configure the system.")

        llm_config = config.config.get("llm_config")
        if not llm_config:
            raise ValueError("GlobalConfig found, but 'llm_config' key is missing.")

        # Validate required steps
        required_steps = ["contextualization", "rag_search", "generation", "complex_reasoning"]
        steps = llm_config.get("steps", {})

        for step in required_steps:
            if step not in steps:
                raise ValueError(f"Missing configuration for step: '{step}' in llm_config.")
            if "model" not in steps[step]:
                raise ValueError(f"Missing 'model' for step '{step}' in llm_config.")

        return llm_config
