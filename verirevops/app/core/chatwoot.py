from app.core.config import settings
import httpx
from typing import Optional
from app.core.logger import Log

class ChatwootClient:
    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.headers = {"api_access_token": self.api_token}

    async def send_message(self, account_id: int, conversation_id: int, content: str, private: bool = False):
        """
        Send a message to a Chatwoot conversation.
        POST /api/v1/accounts/{account_id}/conversations/{conversation_id}/messages
        """
        url = f"{self.base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages"
        payload = {
            "content": content,
            "message_type": "outgoing",
            "private": private
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                Log.error(f"Error sending message to Chatwoot: {e}")
                return None

    async def update_status(self, account_id: int, conversation_id: int, status: str):
        """
        Updates the status of a conversation (open, pending, resolved, snoozed).
        POST /api/v1/accounts/{account_id}/conversations/{conversation_id}/toggle_status
        """
        url = f"{self.base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/toggle_status"
        payload = {"status": status}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                Log.webhook(f"Updated conversation {conversation_id} status to '{status}'", direction="OUT")
                return response.json()
            except httpx.HTTPError as e:
                Log.error(f"Error updating Chatwoot status: {e}")
                return None

# Singleton or dependency injection setup
def get_chatwoot_client() -> Optional[ChatwootClient]:
    url = settings.CHATWOOT_API_URL
    token = settings.CHATWOOT_API_TOKEN
    if not url or not token:
        Log.warning("Chatwoot configuration missing (CHATWOOT_API_URL or CHATWOOT_API_TOKEN)")
        return None
    return ChatwootClient(url, token)
