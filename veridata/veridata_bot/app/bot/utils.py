from typing import Dict, Any, Tuple, Optional

def extract_contact_info(payload: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Robustly extracts contact info (email, phone, name) from a generic webhook payload.
    Checks top-level fields first, then nested 'contact' or 'sender' objects.

    Returns dict with keys: 'email', 'phone', 'name'
    """
    # 1. Try direct access
    email = payload.get("email")
    phone = payload.get("phone_number") or payload.get("phone")
    name = payload.get("name")

    # 2. Try nested 'contact' object (Common in Chatwoot/others)
    if not email and not phone:
        contact = payload.get("contact")
        if isinstance(contact, dict):
            email = contact.get("email")
            phone = contact.get("phone_number") or contact.get("phone")
            name = contact.get("name")

    # 3. Try nested 'sender' object (Sometimes used in event payloads)
    if not email and not phone:
        sender = payload.get("sender") or payload.get("meta", {}).get("sender")
        if isinstance(sender, dict):
             email = sender.get("email")
             phone = sender.get("phone_number") or sender.get("phone")
             name = sender.get("name")

    return {
        "email": email,
        "phone": phone,
        "name": name or "Unknown"
    }

def parse_name(full_name: str) -> Tuple[str, str]:
    """
    Splits a full name into (first_name, last_name).

    Examples:
    "John Doe" -> ("John", "Doe")
    "John" -> ("John", "")
    "John Middle Doe" -> ("John", "Middle Doe")
    "" -> ("", "")
    """
    if not full_name:
        return "", ""

    parts = full_name.strip().split(" ", 1)
    first_name = parts[0]

    if len(parts) > 1:
        last_name = parts[1]
    else:
        last_name = ""

    return first_name, last_name
