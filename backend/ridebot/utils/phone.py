"""
Parse, normalize, and format US phone numbers for pickup info.

Accepted input formats (NANP, 10 digits, area code and exchange can't start with 0/1):
`8585551234`, `858-555-1234`, `(858) 555-1234`, `858.555.1234`, `858 555 1234`,
`+1 858 555 1234`, `1-858-555-1234`, `+18585551234`.
"""

import re
from typing import Literal

from ridebot.utils.constants import MAX_PHONE_INPUT_LENGTH

PhoneStatus = Literal["ok", "invalid", "missing"]

_PHONE_RE = re.compile(r"^(?:\+?1[\s.-]?)?\(?([2-9]\d{2})\)?[\s.-]?([2-9]\d{2})[\s.-]?(\d{4})$")


def normalize_phone(raw: str | None) -> str | None:
    """
    Return the 10 bare digits if raw is a valid US number, else None.

    Also returns None for None or blank input.
    """
    if raw is None:
        return None

    stripped = raw.strip()
    if not stripped or len(stripped) > MAX_PHONE_INPUT_LENGTH:
        return None

    match = _PHONE_RE.match(stripped)
    if match is None:
        return None

    return "".join(match.groups())


def format_phone(stored: str | None) -> str | None:
    """
    Format a stored phone value for display.

    A 10-digit stored value becomes `(858) 555-1234`. Any other non-blank value is
    returned stripped, as-is. None or blank input returns None.
    """
    if stored is None:
        return None

    stripped = stored.strip()
    if not stripped:
        return None

    if len(stripped) == 10 and stripped.isdigit():
        return f"({stripped[:3]}) {stripped[3:6]}-{stripped[6:]}"

    return stripped


def phone_status(stored: str | None) -> PhoneStatus:
    """Classify a stored phone value as missing, ok, or invalid."""
    if stored is None:
        return "missing"

    stripped = stored.strip()
    if not stripped:
        return "missing"

    if len(stripped) == 10 and stripped.isdigit():
        return "ok"

    return "invalid"
