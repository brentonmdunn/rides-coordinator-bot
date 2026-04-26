"""
Rate limiting configuration using slowapi.

Provides a shared Limiter instance that routes can use to apply per-endpoint
rate limits. The limiter is keyed on the client's remote address so a single
client cannot monopolize expensive endpoints (e.g. the LLM-backed
`/api/group-rides`).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Default limit applies to every route that uses `limiter.limit(...)` without
# overriding. Individual routes can apply tighter limits via decorators.
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
