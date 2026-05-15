"""
Compatibility wrapper for contact sync mappings.

New code should import from src.modules.contact_sync.mappings.
"""

from src.modules.contact_sync.mappings import (
    get_contact_mapping,
    svc_create_contact_mapping,
    svc_delete_contact_mapping,
    svc_list_contact_mappings,
    svc_update_contact_mapping,
    upsert_contact_mapping,
)

__all__ = [
    "get_contact_mapping",
    "svc_create_contact_mapping",
    "svc_delete_contact_mapping",
    "svc_list_contact_mappings",
    "svc_update_contact_mapping",
    "upsert_contact_mapping",
]

