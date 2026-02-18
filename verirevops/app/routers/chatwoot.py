from fastapi import APIRouter
from typing import List, Optional

router = APIRouter(tags=["chatwoot"])

@router.get("/webhook/{alias}")
async def get_tenants(alias: str, webhook_data: dict):
    print(f"Received webhook for alias: {alias}")
    print(f"Webhook data: {webhook_data}")
    return {"status": "ok", "message": "Tenant created successfully"}