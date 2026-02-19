"""
API Constants

Centralized configuration constants for the API layer.
"""

import os

ADMIN_EMAILS = {e.strip() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
