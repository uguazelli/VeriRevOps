from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict

class IntegrationConfigBase(BaseModel):
    service_name: str
    url: Optional[str] = None
    api_key: Optional[str] = None
    account_id: Optional[str] = None
    additional_config: Dict[str, Any] = {}
    is_active: bool = True

class IntegrationConfigCreate(IntegrationConfigBase):
    tenant_id: int

class IntegrationConfigUpdate(BaseModel):
    url: Optional[str] = None
    api_key: Optional[str] = None
    account_id: Optional[str] = None
    additional_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class IntegrationConfigs(IntegrationConfigBase):
    id: int
    tenant_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
