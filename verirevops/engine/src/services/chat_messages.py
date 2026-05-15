"""
Compatibility wrapper for Chatwoot message tracking.

New code should import from src.modules.chatwoot.message_tracking.
"""

from src.modules.chatwoot.message_tracking import (
    svc_list_chat_messages,
    svc_upsert_chat_message,
)

__all__ = [
    "svc_list_chat_messages",
    "svc_upsert_chat_message",
]

