from fastapi import APIRouter, HTTPException
from app.services.crm import sync_lead_to_crm
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1", tags=["api"])

class LeadModel(BaseModel):
    firstName: str
    lastName: str
    status: str = "New"
    source: str = "Call"
    opportunityAmount: float = 0
    opportunityAmountCurrency: str = "USD"
    emailAddress: str
    phoneNumber: str

@router.post("/{tenant_slug}/lead")
async def create_lead(tenant_slug: str, lead: LeadModel):
    # Pass the Pydantic model as a dict
    result = await sync_lead_to_crm(tenant_slug, lead.model_dump())
    return result
