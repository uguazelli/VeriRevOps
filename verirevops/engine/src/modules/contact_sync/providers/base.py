from abc import ABC, abstractmethod
from typing import Any

from src.modules.contact_sync.schemas import NormalizedContact


class CrmContactProvider(ABC):
    service_name: str

    @abstractmethod
    async def find_contact(self, contact: NormalizedContact) -> dict[str, Any] | None:
        pass

    @abstractmethod
    async def find_lead(self, contact: NormalizedContact) -> dict[str, Any] | None:
        pass

    @abstractmethod
    async def create_contact(self, contact: NormalizedContact) -> dict[str, Any]:
        pass

    @abstractmethod
    async def create_lead(self, contact: NormalizedContact) -> dict[str, Any]:
        pass

    @abstractmethod
    async def update_contact(self, external_id: str, contact: NormalizedContact) -> dict[str, Any]:
        pass

    @abstractmethod
    async def update_lead(self, external_id: str, contact: NormalizedContact) -> dict[str, Any]:
        pass
