"""
API Constants

Centralized configuration constants for the API layer.
"""

import os

ADMIN_EMAILS = {e.strip() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}

# Server
API_HOST = "0.0.0.0"
API_PORT = 8000

# CORS
CORS_LOCALHOST_5173 = "http://localhost:5173"
CORS_LOCALHOST_5174 = "http://localhost:5174"

# Cloudflare auth
CF_KEYS_CACHE_TTL_SECONDS = 3600.0
CF_KEYS_HTTP_TIMEOUT = 10.0

# Rate limits
DEFAULT_RATE_LIMIT = "120/minute"
GROUP_RIDES_RATE_LIMIT = "10/minute"

# Internal bot-to-API auth
INTERNAL_SECRET_HEADER = "X-Internal-Secret"
INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "")

# Session / cookies
SESSION_COOKIE_NAME = "rides_session"
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
SESSION_TTL_DAYS = 30
SESSION_TTL_SECONDS = SESSION_TTL_DAYS * 24 * 60 * 60

# OAuth state cookie
OAUTH_STATE_COOKIE_MAX_AGE = 600  # 10 minutes

# Discord API URLs
DISCORD_OAUTH_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_OAUTH_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_INFO_URL = "https://discord.com/api/users/@me"
DISCORD_HTTP_TIMEOUT = 10.0

# Emergency bypass
BYPASS_SESSION_TTL = 24 * 60 * 60  # 24 hours

# Access log rotation
ACCESS_LOG_MAX_BYTES = 20 * 1024 * 1024  # 20 MB
ACCESS_LOG_BACKUP_COUNT = 10

# SSE
SSE_HEARTBEAT_INTERVAL = 30  # seconds

# Ask rides defaults
ASK_RIDES_DEFAULT_COUNT = 6
ASK_RIDES_DEFAULT_OFFSET = 0

# Group rides defaults
GROUP_RIDES_DEFAULT_CAPACITY = "44444"

# Frontend URL (local dev default)
FRONTEND_BASE_URL_LOCAL = "http://localhost:5173"
