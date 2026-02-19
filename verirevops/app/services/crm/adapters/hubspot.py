import httpx
from typing import Dict, Any, Optional
from app.services.crm.adapters.base import BaseCRMAdapter
from app.core.logger import Log

class HubSpotAdapter(BaseCRMAdapter):
    """
    HubSpot CRM implementation.
    Reference: https://developers.hubspot.com/docs/api/crm/contacts
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.hubapi.com/crm/v3/objects/contacts"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def create_contact(self, contact_data: Dict[str, Any]) -> Optional[str]:
        """
        Creates a contact in HubSpot.
        Chatwoot contact data is mapped to HubSpot properties.
        """
        properties = self._map_chatwoot_to_hubspot(contact_data)
        payload = {"properties": properties}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(self.base_url, json=payload, headers=self.headers)

                if response.status_code in [200, 201]:
                    Log.success("Contact created in HubSpot")
                    return response.json().get("id")

                Log.error(f"HubSpot create contact failed: {response.status_code} - {response.text}")
                return None
            except httpx.HTTPError as e:
                Log.error(f"HTTP Error connecting to HubSpot: {e}")
                return None

    async def update_contact(self, external_id: str, contact_data: Dict[str, Any]) -> bool:
        """Updates a contact in HubSpot."""
        properties = self._map_chatwoot_to_hubspot(contact_data)
        payload = {"properties": properties}
        url = f"{self.base_url}/{external_id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.patch(url, json=payload, headers=self.headers)
                return response.status_code in [200, 204]
            except httpx.HTTPError as e:
                Log.error(f"HTTP Error updating HubSpot contact: {e}")
                return False

    async def find_contact_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Searches for a contact by email in HubSpot."""
        search_url = f"{self.base_url}/search"
        payload = {
            "filterGroups": [{
                "filters": [{
                    "propertyName": "email",
                    "operator": "EQ",
                    "value": email
                }]
            }]
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(search_url, json=payload, headers=self.headers)
                if response.status_code == 200:
                    results = response.json().get("results", [])
                    return results[0] if results else None
                return None
            except httpx.HTTPError as e:
                Log.error(f"HTTP Error searching HubSpot contact: {e}")
                return None

    def _map_chatwoot_to_hubspot(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Maps Chatwoot contact fields to HubSpot properties."""
        # Clean code: avoid God functions, map only what's needed
        name_parts = (data.get("name") or "").split(" ", 1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        return {
            "email": data.get("email", ""),
            "firstname": first_name,
            "lastname": last_name,
            "phone": data.get("phone_number", ""),
        }
