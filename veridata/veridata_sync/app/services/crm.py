import httpx
import json
from app.db import get_db_connection
from fastapi import HTTPException

async def sync_lead_to_crm(tenant_slug: str, lead_data: dict):
    async with get_db_connection() as conn:
        # 1. Get Tenant
        tenant = await conn.fetchrow("SELECT id FROM tenants WHERE slug = $1", tenant_slug)
        if not tenant:
            raise HTTPException(status_code=404, detail=f"Tenant '{tenant_slug}' not found")

        # 2. Get CRM Config
        config = await conn.fetchrow(
            "SELECT value FROM config WHERE tenant_id = $1 AND key = 'crm'",
            tenant['id']
        )
        if not config:
            raise HTTPException(status_code=400, detail="CRM configuration not found for this tenant")

        crm_config = json.loads(config['value'])

        # Validate Config
        required_keys = ["url", "apikey"]
        for k in required_keys:
            if k not in crm_config:
                 raise HTTPException(status_code=500, detail=f"Invalid CRM config: missing {k}")

        # 3. Prepare Request
        # Mapping: We assume lead_data matches the CRM expectation or we map it here.
        # For now, we pass lead_data directly as requested.

        url = f"{crm_config['url']}/api/v1/Lead"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Api-Key": crm_config['apikey'],
            "X-Duplicate-Source-Id": "false",
            "X-Skip-Duplicate-Check": "false"
        }

        # Add basic validation for required fields in lead_data could go here

        # 4. Execute Request
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=headers, json=lead_data, timeout=10.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                raise HTTPException(status_code=e.response.status_code, detail=f"CRM Error: {e.response.text}")
            except httpx.RequestError as e:
                raise HTTPException(status_code=502, detail=f"Failed to connect to CRM: {e}")
