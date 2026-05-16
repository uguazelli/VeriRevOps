import json
import logging
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException

from src.modules.contact_sync.models import NormalizedContact
from src.modules.contact_sync.providers.base import CrmContactProvider


logger = logging.getLogger(__name__)


class EspoCrmProvider(CrmContactProvider):
    service_name = "espocrm"

    def __init__(self, service_config):
        if not service_config.url or not service_config.api_key:
            raise HTTPException(
                status_code=400,
                detail="EspoCRM service is missing url or api_key",
            )

        self.base_url = service_config.url.rstrip("/") + "/api/v1"
        self.api_key = service_config.api_key

    async def find_contact(self, contact: NormalizedContact) -> Optional[Dict[str, Any]]:
        return await self._find_person_record("Contact", contact)

    async def find_lead(self, contact: NormalizedContact) -> Optional[Dict[str, Any]]:
        return await self._find_person_record("Lead", contact)

    async def get_record(self, entity_type: str, external_id: str) -> Optional[Dict[str, Any]]:
        try:
            return await self._request(
                "GET",
                f"{entity_type}/{external_id}",
                log_not_found_as_error=False,
            )
        except HTTPException as exc:
            if exc.status_code in {403, 404}:
                logger.info(
                    "EspoCRM %s record %s not readable or not found",
                    entity_type,
                    external_id,
                )
                return None

            raise

    async def create_stream_note(
        self,
        parent_type: str,
        parent_id: str,
        post: str,
    ) -> Dict[str, Any]:
        return await self._request(
            "POST",
            "Note",
            json_data={
                "type": "Post",
                "parentType": parent_type,
                "parentId": parent_id,
                "post": post,
            },
        )

    async def _find_person_record(
        self,
        entity_type: str,
        contact: NormalizedContact,
    ) -> Optional[Dict[str, Any]]:
        where = self._build_search_where(contact)

        if not where:
            return None

        response = await self._request(
            "GET",
            entity_type,
            params={
                "searchParams": json.dumps({
                    "select": ["id", "name", "firstName", "lastName", "emailAddress", "phoneNumber"],
                    "maxSize": 1,
                    "where": where,
                })
            },
        )
        records = response.get("list") or []

        if not records:
            return None

        return records[0]

    async def create_contact(self, contact: NormalizedContact) -> Dict[str, Any]:
        return await self._request(
            "POST",
            "Contact",
            json_data=self._build_person_payload(contact),
        )

    async def create_lead(self, contact: NormalizedContact) -> Dict[str, Any]:
        return await self._request(
            "POST",
            "Lead",
            json_data=self._build_lead_payload(contact),
        )

    async def update_contact(self, external_id: str, contact: NormalizedContact) -> Dict[str, Any]:
        return await self._request(
            "PUT",
            f"Contact/{external_id}",
            json_data=self._build_person_payload(contact),
        )

    async def update_lead(self, external_id: str, contact: NormalizedContact) -> Dict[str, Any]:
        return await self._request(
            "PUT",
            f"Lead/{external_id}",
            json_data=self._build_lead_payload(contact),
        )

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        log_not_found_as_error: bool = True,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"

        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.request(
                method,
                url,
                headers={
                    "X-Api-Key": self.api_key,
                    "Content-Type": "application/json",
                },
                params=params,
                json=json_data,
                timeout=30.0,
            )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_reason = response.headers.get("x-status-reason")
            error_text = response.text[:500] if response.text else ""
            if response.status_code == 404 and not log_not_found_as_error:
                logger.info(
                    "EspoCRM request returned not found: %s %s reason=%s",
                    method,
                    path,
                    status_reason,
                )
            else:
                logger.exception(
                    "EspoCRM request failed: %s %s status=%s reason=%s response=%s",
                    method,
                    path,
                    response.status_code,
                    status_reason,
                    error_text,
                )
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=status_reason or "EspoCRM contact sync request failed",
            ) from exc

        if not response.content:
            return {}

        return response.json()

    def _build_search_where(self, contact: NormalizedContact):
        conditions = []

        if contact.email:
            conditions.append({
                "type": "equals",
                "attribute": "emailAddress",
                "value": contact.email,
            })

        if contact.phone:
            conditions.append({
                "type": "equals",
                "attribute": "phoneNumber",
                "value": contact.phone,
            })

        if len(conditions) > 1:
            return [{"type": "or", "value": conditions}]

        return conditions

    def _build_person_payload(self, contact: NormalizedContact) -> Dict[str, Any]:
        payload = {}

        if contact.first_name:
            payload["firstName"] = contact.first_name

        payload["lastName"] = (
            contact.last_name
            or contact.name
            or contact.email
            or contact.phone
            or "Unknown"
        )

        if contact.email:
            payload["emailAddress"] = contact.email

        if contact.phone:
            payload["phoneNumber"] = contact.phone

        return payload

    def _build_lead_payload(self, contact: NormalizedContact) -> Dict[str, Any]:
        payload = self._build_person_payload(contact)

        if contact.company_name:
            payload["accountName"] = contact.company_name

        return payload
