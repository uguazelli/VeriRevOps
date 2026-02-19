from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseCRMAdapter(ABC):
    """
    Abstract base class for CRM adapters.
    Ensures a consistent interface for different CRM providers.
    """

    @abstractmethod
    async def create_contact(self, contact_data: Dict[str, Any]) -> Optional[str]:
        """
        Creates a contact/lead in the CRM.
        Returns the CRM-specific ID of the created contact.
        """
        pass

    @abstractmethod
    async def update_contact(self, external_id: str, contact_data: Dict[str, Any]) -> bool:
        """
        Updates an existing contact in the CRM.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    async def find_contact_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Searches for a contact by email.
        Returns the contact data if found, None otherwise.
        """
        pass

    @abstractmethod
    async def add_note(self, external_id: str, title: str, content: str) -> bool:
        """
        Adds a note or log entry to an existing contact.
        Returns True if successful, False otherwise.
        """
        pass
