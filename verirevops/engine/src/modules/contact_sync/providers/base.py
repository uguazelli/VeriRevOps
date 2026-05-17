from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.modules.contact_sync.schemas import NormalizedContact


class CrmContactProvider(ABC):
    service_name: str

    @abstractmethod
    async def find_contact(self, contact: NormalizedContact) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    async def find_lead(self, contact: NormalizedContact) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    async def create_contact(self, contact: NormalizedContact) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def create_lead(self, contact: NormalizedContact) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def update_contact(self, external_id: str, contact: NormalizedContact) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def update_lead(self, external_id: str, contact: NormalizedContact) -> Dict[str, Any]:
        pass
