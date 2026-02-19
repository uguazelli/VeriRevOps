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
                Log.info(f"Sending message to Chatwoot (Account: {account_id}, Conv: {conversation_id})")
                response = await client.post(url, json=payload, headers=self.headers)

                if response.status_code not in [200, 201]:
                    Log.error(f"Failed to send message. Status: {response.status_code}")
                    Log.error(f"Response headers: {dict(response.headers)}")
                    Log.error(f"Response body: {response.text[:1000]}")
                    Log.error(f"Payload sent: {payload}")

                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                Log.error(f"HTTP Error sending message to Chatwoot: {e}")
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

                if response.status_code not in [200, 201]:
                    Log.error(f"Failed to update status. Status: {response.status_code}")
                    Log.error(f"Response headers: {dict(response.headers)}")
                    Log.error(f"Response body: {response.text[:1000]}")

                response.raise_for_status()
                Log.webhook(f"Updated conversation {conversation_id} status to '{status}'", direction="OUT")
                return response.json()
            except httpx.HTTPError as e:
                Log.error(f"HTTP Error updating Chatwoot status: {e}")
                return None

    async def get_file(self, url: str) -> Optional[bytes]:
        """
        Downloads a file from Chatwoot.
        Initial attempt includes 'api_access_token'.
        If it fails (common with Active Storage signed URLs), retries without headers.
        """
        async with httpx.AsyncClient(follow_redirects=True) as client:
            # 1. Try with authentication headers
            try:
                Log.info(f"Attempting download (with auth): {url}")
                response = await client.get(url, headers=self.headers)
                if response.status_code == 200:
                    return response.content

                Log.warning(f"Download with auth failed (Status: {response.status_code}). Retrying without auth...")
            except httpx.HTTPError as e:
                Log.warning(f"HTTP Error with auth: {e}. Retrying without auth...")

            # 2. Try without authentication headers (Fallback for signed URLs)
            try:
                Log.info(f"Attempting download (no auth): {url}")
                response = await client.get(url)
                if response.status_code == 200:
                    Log.success("Download successful without authentication headers.")
                    return response.content

                Log.error(f"Download failed again (Status: {response.status_code})")
                Log.error(f"Response headers: {dict(response.headers)}")
                if "text" in response.headers.get("Content-Type", ""):
                    Log.error(f"Error body snippet: {response.text[:500]}")

                return None
            except httpx.HTTPError as e:
                Log.error(f"HTTP Error without auth: {e}")
                return None

# Singleton or dependency injection setup
def get_chatwoot_client() -> Optional[ChatwootClient]:
    url = settings.CHATWOOT_API_URL
    token = settings.CHATWOOT_API_TOKEN
    if not url or not token:
        Log.warning("Chatwoot configuration missing (CHATWOOT_API_URL or CHATWOOT_API_TOKEN)")
        return None
    return ChatwootClient(url, token)
