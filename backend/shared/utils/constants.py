"""Constants used by shared infrastructure."""

import pytz

# Timezone
# Every bot schedules and formats against LA time, so this lives in shared rather
# than in any one bot package.
LA_TZ = pytz.timezone("America/Los_Angeles")

# Lifecycle
REDIS_CONNECTION_TIMEOUT = 5.0

# Frontend URL (local dev default). The real value comes from the FRONTEND_BASE_URL env var.
FRONTEND_BASE_URL_LOCAL = "http://localhost:5173"

# Session / auth
SESSION_TTL_DAYS = 30
SESSION_TOUCH_THROTTLE_MINUTES = 5
