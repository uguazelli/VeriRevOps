from app.services.crm.adapters.hubspot import HubSpotAdapter
from app.services.crm.adapters.espocrm import EspoCRMAdapter
from app.models.integration import IntegrationConfig
from typing import Optional
from app.services.crm.adapters.base import BaseCRMAdapter

class CRMFactory:
    """
    Factory to create the appropriate CRM adapter based on tenant configuration.
    """

    @staticmethod
    def get_adapter(config: IntegrationConfig) -> Optional[BaseCRMAdapter]:
        """
        Returns an instance of the configured CRM adapter.
        """
        # Guard clause: inactive configuration
        if not config.is_active:
            return None

        # Clean code: use a simple mapping instead of nested if-else if possible
        adapters = {
            "hubspot": lambda: HubSpotAdapter(api_key=config.api_key),
            "espocrm": lambda: EspoCRMAdapter(url=config.url, api_key=config.api_key),
        }

        adapter_creator = adapters.get(config.service_name.lower())

        if not adapter_creator:
            return None

        return adapter_creator()
