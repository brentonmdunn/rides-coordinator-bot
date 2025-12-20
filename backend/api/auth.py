"""
Cloudflare Access Authentication

This module handles JWT verification for Cloudflare Access.
"""

import logging
import os

import httpx
from fastapi import Request, Response
from jose import jwt

logger = logging.getLogger(__name__)

# Cloudflare Access Configuration
CLOUDFLARE_TEAM_DOMAIN = os.getenv("CLOUDFLARE_TEAM_DOMAIN")
CLOUDFLARE_AUD = os.getenv("CLOUDFLARE_AUD")
APP_ENV = os.getenv("APP_ENV", "local")

# Cache for Cloudflare public keys
_cloudflare_keys = None


async def get_cloudflare_keys():
    """
    Fetch and cache public keys from Cloudflare.
    
    Returns:
        List of public keys or empty list if fetch fails.
    """
    global _cloudflare_keys
    if _cloudflare_keys is None:
        if not CLOUDFLARE_TEAM_DOMAIN:
            logger.warning("CLOUDFLARE_TEAM_DOMAIN environment variable is not set")
            return []
        url = f"https://{CLOUDFLARE_TEAM_DOMAIN}/cdn-cgi/access/certs"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                _cloudflare_keys = resp.json()["keys"]
                logger.info("Successfully fetched Cloudflare public keys")
        except Exception as e:
            logger.error(f"Failed to fetch Cloudflare keys from {url}: {e}")
            return []
    return _cloudflare_keys


async def verify_cloudflare_token(request: Request):
    """
    Verifies the Cloudflare Access JWT and extracts user information.
    
    Args:
        request: The FastAPI request object
        
    Returns:
        User info dict or None if verification fails.
    """
    if APP_ENV == "local":
        # Return mock user for dev mode
        return {"email": "dev@example.com", "sub": "dev-user"}

    if not CLOUDFLARE_AUD or not CLOUDFLARE_TEAM_DOMAIN:
        logger.error("Cloudflare Access configuration is missing (CLOUDFLARE_AUD or CLOUDFLARE_TEAM_DOMAIN)")
        return None

    # Allow health check to bypass auth
    if request.url.path == "/health":
        return {"email": "health-check", "sub": "system"}

    token = request.headers.get("Cf-Access-Jwt-Assertion")
    if not token:
        logger.error(f"Missing Cf-Access-Jwt-Assertion header for path: {request.url.path}")
        return None
    
    keys = await get_cloudflare_keys()
    
    try:
        header = jwt.get_unverified_header(token)
        key = next(k for k in keys if k["kid"] == header["kid"])
        
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=CLOUDFLARE_AUD,
            issuer=f"https://{CLOUDFLARE_TEAM_DOMAIN}"
        )
        
        # Extract user information from JWT payload
        return {
            "email": payload.get("email"),
            "sub": payload.get("sub"),
            "name": payload.get("name")
        }
    except Exception as e:
        # Debug logging for troubleshooting 'Invalid audience' or 'Invalid issuer'
        try:
            unverified_payload = jwt.get_unverified_claims(token)
            logger.error(
                f"Token verification failed for {request.url.path}: {e} | "
                f"Token data -> aud: {unverified_payload.get('aud')} | "
                f"iss: {unverified_payload.get('iss')}"
            )
        except Exception:
            logger.error(f"Token verification failed for {request.url.path}: {e} (could not parse unverified claims)")
        return None


async def cloudflare_access_middleware(request: Request, call_next):
    """
    HTTP middleware to verify Cloudflare Access JWT on all requests.
    
    Args:
        request: The FastAPI request object
        call_next: The next middleware/handler in the chain
        
    Returns:
        Response from next handler or 401 Unauthorized
    """
    user_info = await verify_cloudflare_token(request)
    if user_info:
        request.state.user = user_info  # Attach user info to request
        response = await call_next(request)
        return response
    return Response(content="Unauthorized", status_code=401)
