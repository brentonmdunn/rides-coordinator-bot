"""
Access Logging Middleware

This middleware logs all HTTP requests to a separate access log file with
structured information including timing, status codes, and user context.
"""

import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# Configure access logger
access_logger = logging.getLogger("api.access")
access_logger.setLevel(logging.INFO)
access_logger.propagate = False  # Don't propagate to root logger

# Create separate access log file
LOG_DIR = Path(__file__).parent.parent.parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
ACCESS_LOG_FILE = LOG_DIR / "access.log"

# Rotating file handler for access logs
access_file_handler = RotatingFileHandler(
    ACCESS_LOG_FILE,
    maxBytes=20 * 1024 * 1024,  # 20 MB (access logs can be larger)
    backupCount=10,  # Keep more history for access logs
    encoding="utf-8",
)

# Access log format: Apache Combined Log Format style
access_formatter = logging.Formatter("%(asctime)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
access_file_handler.setFormatter(access_formatter)
access_logger.addHandler(access_file_handler)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log HTTP access in a structured format.

    Logs include:
    - Client IP
    - HTTP method and path
    - Status code
    - Response time
    - User agent
    - Authenticated user (if available)
    """

    async def dispatch(self, request: Request, call_next):
        """
        Process request and log access information.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or route handler

        Returns:
            The HTTP response
        """
        # Start timing
        start_time = time.time()

        # Get client IP (handle proxies)
        client_ip = request.client.host if request.client else "unknown"
        if "x-forwarded-for" in request.headers:
            client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Get user info from request state (set by auth middleware)
        user_info = getattr(request.state, "user", None)
        user_email = user_info.get("email", "-") if user_info else "-"

        # Get user agent
        user_agent = request.headers.get("user-agent", "-")

        # Log in structured format
        log_message = (
            f"{client_ip} - {user_email} - "
            f'"{request.method} {request.url.path}" '
            f"{response.status_code} - "
            f"{duration_ms:.2f}ms - "
            f'"{user_agent}"'
        )

        # Skip logging for successful health checks
        if request.url.path == "/health" and response.status_code == 200:
            return response

        # Use different log levels based on status code
        if response.status_code >= 500:
            access_logger.error(log_message)
        elif response.status_code >= 400:
            access_logger.warning(log_message)
        else:
            access_logger.info(log_message)

        return response
