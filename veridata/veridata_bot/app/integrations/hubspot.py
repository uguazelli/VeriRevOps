import logging
import httpx
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class HubSpotClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.hubapi.com"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    async def _search_contact(self, email: Optional[str] = None, phone: Optional[str] = None) -> Optional[str]:
        """
        Search for a contact by email or phone. Returns the Contact ID if found.
        """
        url = f"{self.base_url}/crm/v3/objects/contacts/search"

        filters = []
        if email:
            filters.append({
                "propertyName": "email",
                "operator": "EQ",
                "value": email
            })

        filter_groups = []
        if email:
            filter_groups.append({
                "filters": [{
                    "propertyName": "email",
                    "operator": "EQ",
                    "value": email
                }]
            })
        if phone:
             filter_groups.append({
                "filters": [{
                    "propertyName": "phone",
                    "operator": "EQ",
                    "value": phone
                }]
            })

        if not filter_groups:
            return None

        payload = {
            "filterGroups": filter_groups,
            "properties": ["id", "email", "firstname", "lastname"],
            "limit": 1
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self.headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                if data["total"] > 0:
                    return data["results"][0]["id"]
            else:
                logger.error(f"HubSpot Search Error: {resp.text}")

        return None

    async def sync_lead(self, name: str, email: Optional[str] = None, phone_number: Optional[str] = None):
        """
        Creates or updates a contact in HubSpot.
        """
        if not email and not phone_number:
            logger.warning("HubSpot: Cannot sync lead without email or phone")
            return

        existing_id = await self._search_contact(email, phone_number)

        properties = {}
        if email: properties["email"] = email
        if phone_number: properties["phone"] = phone_number

        # Split name if possible
        if name:
            parts = name.split(" ", 1)
            properties["firstname"] = parts[0]
            if len(parts) > 1:
                properties["lastname"] = parts[1]
            else:
                properties["lastname"] = "Unknown"

        async with httpx.AsyncClient() as client:
            if existing_id:
                # Update
                url = f"{self.base_url}/crm/v3/objects/contacts/{existing_id}"
                await client.patch(url, headers=self.headers, json={"properties": properties})
                logger.info(f"HubSpot: Updated contact {existing_id}")
            else:
                # Create
                url = f"{self.base_url}/crm/v3/objects/contacts"
                resp = await client.post(url, headers=self.headers, json={"properties": properties})
                if resp.status_code == 201:
                    logger.info("HubSpot: Created new contact")
                else:
                    logger.error(f"HubSpot Create Error: {resp.text}")

    async def sync_contact(self, payload: Dict[str, Any]):
        """
        Syncs a contact object (usually from Chatwoot payload) to HubSpot.
        """
        # Try direct access (standard contact payload)
        email = payload.get("email")
        phone = payload.get("phone_number")
        name = payload.get("name")

        # Fallback: Sometimes generic webhook wraps it in 'payload' or 'contact'
        if not email and not phone:
             # Check if it is inside 'contact' key (common in some webhooks)
             contact_data = payload.get("contact")
             if isinstance(contact_data, dict):
                 email = contact_data.get("email")
                 phone = contact_data.get("phone_number")
                 name = contact_data.get("name")

        await self.sync_lead(name, email, phone)

    async def update_lead_summary(self, email: Optional[str], phone: Optional[str], summary_data: Dict[str, Any]):
        """
        Adds a note to the contact with the conversation summary.
        """
        contact_id = await self._search_contact(email, phone)
        if not contact_id:
            logger.warning("HubSpot: Could not find contact to attach summary")
            return

        # Format the summary as a readable Note (HubSpot supports HTML)
        from app.bot.formatting import ConversationFormatter
        formatter = ConversationFormatter(summary_data)
        note_body = formatter.to_html()

        # Create Engagement (Note)
        # HubSpot V3 supports associating notes directly to valid objects
        url = f"{self.base_url}/crm/v3/objects/notes"

        note_properties = {
            "hs_note_body": note_body
        }

        # HubSpot requires hs_timestamp. Use summary time or fallback to now.
        import time
        ts_ms = int(time.time() * 1000) # Default to now

        if summary_data.get("end_timestamp"):
            try:
                # Expecting unix timestamp (float or int)
                # Ensure we have a valid number
                ts_val = float(summary_data["end_timestamp"])
                if ts_val > 0:
                    ts_ms = int(ts_val * 1000)
            except (ValueError, TypeError):
                logger.warning(f"HubSpot: Invalid timestamp {summary_data.get('end_timestamp')}, using current time")

        note_properties["hs_timestamp"] = str(ts_ms)

        payload = {
            "properties": note_properties,
            "associations": [
                {
                    "to": {"id": contact_id},
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}] # 202 is Note to Contact
                }
            ]
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self.headers, json=payload)
            if resp.status_code == 201:
                logger.info(f"HubSpot: Added summary note to contact {contact_id}")
            else:
                logger.error(f"HubSpot Note Error: {resp.text}")
