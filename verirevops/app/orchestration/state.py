from typing import List, TypedDict, Annotated
from langchain_core.messages import BaseMessage

class ChatState(TypedDict):
    tenant_id: Annotated[int, "The ID of the tenant"]
    account_id: Annotated[int, "The Chatwoot account ID"]
    session_id: Annotated[int, "The ID of the chat session"]
    user_message: Annotated[str, "The message from the user"]
    chat_history: Annotated[List[BaseMessage], "The history of the chat"]
    intent: Annotated[str, "The classified intent: rag, chitchat, or handoff"]
    ai_response: Annotated[str, "The response from the AI"]
    summary_needed: Annotated[bool, "Whether a summary update is required"]
    attachments: Annotated[List[dict], "Media attachments from Chatwoot"]
