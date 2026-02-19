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
        """
        url = f"{self.base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages"
        payload = {"content": content, "message_type": "outgoing", "private": private}

        async with httpx.AsyncClient() as client:
            try:
                Log.info(f"Sending message to Chatwoot (Account: {account_id}, Conv: {conversation_id})")
                response = await client.post(url, json=payload, headers=self.headers)

                if response.status_code not in [200, 201]:
                    self._log_response_error("send_message", response, payload)

                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                Log.error(f"HTTP Error sending message to Chatwoot: {e}")
                return None

    async def update_status(self, account_id: int, conversation_id: int, status: str):
        """
        Updates the status of a conversation (open, pending, resolved, snoozed).
        """
        url = f"{self.base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/toggle_status"
        payload = {"status": status}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=self.headers)
                if response.status_code not in [200, 201]:
                    self._log_response_error("update_status", response, payload)

                response.raise_for_status()
                Log.webhook(f"Updated conversation {conversation_id} status to '{status}'", direction="OUT")
                return response.json()
            except httpx.HTTPError as e:
                Log.error(f"HTTP Error updating Chatwoot status: {e}")
                return None

    async def get_file(self, url: str) -> Optional[bytes]:
        """
        Downloads a file from Chatwoot, attempting with auth first then without (for signed URLs).
        """
        async with httpx.AsyncClient(follow_redirects=True) as client:
            # 1. Attempt with authentication
            data = await self._attempt_download(client, url, headers=self.headers)
            if data:
                return data

            # 2. Attempt without authentication (Fallback for signed URLs)
            Log.warning("Download with auth failed or skipped. Retrying without auth...")
            return await self._attempt_download(client, url, headers=None)

    async def _attempt_download(self, client: httpx.AsyncClient, url: str, headers: Optional[dict]) -> Optional[bytes]:
        """Helper to try downloading a file and handle basic status checks."""
        try:
            desc = "with auth" if headers else "no auth"
            Log.info(f"Attempting download ({desc}): {url}")
            response = await client.get(url, headers=headers)

            if response.status_code == 200:
                if not headers:
                    Log.success("Download successful without authentication headers.")
                return response.content

            Log.error(f"Download failed ({desc}). Status: {response.status_code}")
            if "text" in response.headers.get("Content-Type", ""):
                 Log.error(f"Error body snippet: {response.text[:500]}")

        except httpx.HTTPError as e:
            Log.warning(f"HTTP Error ({desc}): {e}")

        return None

    def _log_response_error(self, method: str, response: httpx.Response, payload: dict = None):
        """Standardized error logging for Chatwoot API responses."""
        Log.error(f"Failed {method}. Status: {response.status_code}")
        Log.error(f"Response headers: {dict(response.headers)}")
        Log.error(f"Response body: {response.text[:1000]}")
        if payload:
            Log.error(f"Payload sent: {payload}")

# Singleton or dependency injection setup
def get_chatwoot_client() -> Optional[ChatwootClient]:
    url = settings.CHATWOOT_API_URL
    token = settings.CHATWOOT_API_TOKEN
    if not url or not token:
        Log.warning("Chatwoot configuration missing (CHATWOOT_API_URL or CHATWOOT_API_TOKEN)")
        return None
    return ChatwootClient(url, token)
