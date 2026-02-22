import asyncio
import httpx
from typing import Optional
from app.core.config import settings
from app.core.logger import Log
from app.core.decorators import with_retries

class ChatwootClient:
    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.headers = {"api_access_token": self.api_token}

    @with_retries(attempts=3, log_message="Chatwoot send_message failed")
    async def send_message(self, account_id: int, conversation_id: int, content: str, private: bool = False):
        """
        Send a message to a Chatwoot conversation.
        """
        url = f"{self.base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages"
        payload = {"content": content, "message_type": "outgoing", "private": private}

        async with httpx.AsyncClient() as client:
            Log.info(f"Sending message to Chatwoot (Acc: {account_id}, Conv: {conversation_id})")
            response = await client.post(url, json=payload, headers=self.headers, timeout=10.0)

            if response.status_code in [200, 201]:
                return response.json()

            response.raise_for_status()
            return None

    @with_retries(attempts=3, log_message="Chatwoot update_status failed")
    async def update_status(self, account_id: int, conversation_id: int, status: str):
        """
        Updates the status of a conversation (open, pending, resolved, snoozed).
        """
        url = f"{self.base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/toggle_status"
        payload = {"status": status}
        async with httpx.AsyncClient() as client:
            Log.info(f"Updating Chatwoot status (Acc: {account_id}, Conv: {conversation_id}) to '{status}'")
            response = await client.post(url, json=payload, headers=self.headers, timeout=10.0)

            if response.status_code in [200, 201]:
                Log.webhook(f"Updated conversation {conversation_id} status to '{status}'", direction="OUT")
                return response.json()

            response.raise_for_status()
            return None

    async def get_conversation(self, account_id: int, conversation_id: int):
        """
        Fetches conversation details.
        """
        url = f"{self.base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers)
                if response.status_code == 200:
                    return response.json()
                self._log_response_error("get_conversation", response)
                return None
            except httpx.HTTPError as e:
                Log.error(f"HTTP Error fetching Chatwoot conversation: {e}")
                return None

    @with_retries(attempts=3, log_message="Chatwoot get_messages failed")
    async def get_messages(self, account_id: int, conversation_id: int, after: Optional[int] = None, before: Optional[int] = None, limit: int = 100):
        """
        Fetches messages for a conversation, optionally after a specific message ID.
        """
        url = f"{self.base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages"
        params = {}
        if after:
            params["after"] = after
        if before:
            params["before"] = before
        if limit:
            params["limit"] = limit

        async with httpx.AsyncClient() as client:
            Log.info(f"GET Chatwoot Messages (Acc: {account_id}, Conv: {conversation_id}) Params: {params}")
            response = await client.get(url, headers=self.headers, params=params, timeout=10.0)

            if response.status_code == 200:
                messages = response.json().get("payload", [])

                # Safety: Filter locally if API didn't strictly respect after/before
                if after is not None:
                    messages = [m for m in messages if m.get("id", 0) > after]
                if before is not None:
                    messages = [m for m in messages if m.get("id", 0) < before]

                # Chatwoot doesn't consistently respect limit params, so we slice.
                # Sort by created_at ascending (oldest first)
                messages = sorted(messages, key=lambda x: x.get("created_at", 0))
                return messages[-limit:] if limit else messages

            response.raise_for_status()
            return []

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
