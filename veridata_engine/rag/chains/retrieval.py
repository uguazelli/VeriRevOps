from typing import List
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough

from bot.core.ai import get_llm
from bot.services.global_config_service import get_llm_config
from utils.prompts import QUERY_EXPANSION_PROMPT_TEMPLATE

async def get_query_expansion_chain():
    """Returns an LCEL chain for Query Expansion."""

    # Fetch dynamic config
    config = await get_llm_config()
    model_name = config["steps"]["rag_search"]["model"]

    llm = get_llm(model_name=model_name, temperature=0.7) # Higher temp for creativity

    prompt = PromptTemplate.from_template(QUERY_EXPANSION_PROMPT_TEMPLATE)

    def parse_expansion(output: str) -> List[str]:
        # Split by newlines and clean up
        questions = [line.strip() for line in output.split("\n") if line.strip()]
        return questions

    chain = (
        {"query": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
        | parse_expansion
    )

    return chain
