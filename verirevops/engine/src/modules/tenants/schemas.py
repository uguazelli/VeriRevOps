from sqlmodel import Field, SQLModel

from src.core.models import ConfigurationBase, ServiceBase, SubscriptionBase, TenantBase
from src.modules.global_config.schemas import GlobalConfigResponse


class SubscriptionResponse(SubscriptionBase):
    id: int


class ConfigurationResponse(ConfigurationBase):
    id: int


class ServiceResponse(ServiceBase):
    id: int


class TenantResponse(TenantBase):
    id: int
    services: dict[str, ServiceResponse] = Field(default_factory=dict)
    subscription: SubscriptionResponse | None = None
    configuration: ConfigurationResponse | None = None


class TenantFullResponse(SQLModel):
    tenant: TenantResponse
    global_config: GlobalConfigResponse | None = None
