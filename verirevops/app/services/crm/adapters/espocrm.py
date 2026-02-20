import httpx
from typing import Dict, Any, Optional
from app.services.crm.adapters.base import BaseCRMAdapter
from app.core.logger import Log

class EspoCRMAdapter(BaseCRMAdapter):
    """
    EspoCRM implementation.
    Reference: https://docs.espocrm.com/development/api/
    """

    def __init__(self, url: str, api_key: str):
        self.url = url.rstrip('/')
        self.api_key = api_key
        # EspoCRM usually uses X-Api-Key or basic auth
        self.headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }

    async def create_contact(self, contact_data: Dict[str, Any]) -> Optional[str]:
        """Creates a Lead in EspoCRM."""
        # Using Lead as default for new contacts
        url = f"{self.url}/api/v1/Lead"
        payload = self._map_chatwoot_to_espo(contact_data)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=self.headers)

                if response.status_code in [200, 201]:
                    Log.success("Lead created in EspoCRM")
                    return response.json().get("id")

                Log.error(f"EspoCRM create lead failed: {response.status_code} - {response.text}")
                return None
            except httpx.HTTPError as e:
                Log.error(f"HTTP Error connecting to EspoCRM: {e}")
                return None

    async def update_contact(self, external_id: str, contact_data: Dict[str, Any]) -> bool:
        """Updates a Lead in EspoCRM."""
        url = f"{self.url}/api/v1/Lead/{external_id}"
        payload = self._map_chatwoot_to_espo(contact_data)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.put(url, json=payload, headers=self.headers)
                return response.status_code in [200, 204]
            except httpx.HTTPError as e:
                Log.error(f"HTTP Error updating EspoCRM lead: {e}")
                return False

    async def add_note(self, external_id: str, title: str, content: str) -> bool:
        """
        Adds a post to the entity stream in EspoCRM.
        """
        url = f"{self.url}/api/v1/Note"

        # Format: Espo posts are usually Markdown or plain text
        full_text = f"### {title}\n\n{content}"

        payload = {
            "post": full_text,
            "parentType": "Lead", # Defaulting to Lead as per our creation flow
            "parentId": external_id,
            "type": "Post"
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=self.headers)
                if response.status_code in [200, 201]:
                    Log.success(f"Summary post added to EspoCRM stream for {external_id}")
                    return True

                Log.error(f"Failed to add note to EspoCRM: {response.status_code} - {response.text}")
                return False
            except httpx.HTTPError as e:
                Log.error(f"HTTP Error adding EspoCRM note: {e}")
                return False

    async def find_contact_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Searches for a Lead by email in EspoCRM."""
        import json

        url = f"{self.url}/api/v1/Lead"
        # Using the searchParams structure which is more robust in some Espo versions
        where = [
            {"type": "equals", "attribute": "emailAddress", "value": email}
        ]
        params = {"where": json.dumps(where)}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, headers=self.headers)
                if response.status_code == 200:
                    data = response.json()
                    collection = data.get("list", [])

                    if collection:
                        first_result = collection[0]
                        res_email = first_result.get('emailAddress', '').lower()

                        # Validation: Ensure it's not just returning the first record in the DB
                        if res_email == email.lower():
                            return first_result
                        else:
                            Log.warning(f"EspoCRM search returned non-matching result (Search: {email}, Got: {res_email}). Ignoring.")
                            return None
                    return None

                return None
            except httpx.HTTPError as e:
                Log.error(f"HTTP Error searching EspoCRM lead: {e}")
                return None

    def _map_chatwoot_to_espo(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Maps Chatwoot contact fields to EspoCRM lead fields."""
        name_parts = (data.get("name") or "").split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else "Unknown" # Espo often requires last name

        return {
            "firstName": first_name,
            "lastName": last_name,
            "emailAddress": data.get("email", ""),
            "phoneNumber": data.get("phone_number", ""),
            "description": f"Created from Chatwoot. Source ID: {data.get('id')}"
        }
