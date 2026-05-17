from abc import ABC, abstractmethod

from src.modules.conversation_summary.schemas import CrmSummaryTarget


class ConversationSummaryCrmHandler(ABC):
    service_name: str

    def __init__(self, tenant_settings, provider):
        self.tenant_settings = tenant_settings
        self.provider = provider

    @abstractmethod
    async def resolve_summary_target(self, payload: dict) -> CrmSummaryTarget:
        pass

    @abstractmethod
    async def send_summary(self, target: CrmSummaryTarget, summary: str):
        pass
