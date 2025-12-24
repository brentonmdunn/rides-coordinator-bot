FROM python:3.13-slim AS builder

# Install system dependencies needed for building
RUN apt update && apt install -y curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh

WORKDIR /app

# Copy only dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies into a virtual environment
RUN uv sync --no-cache --no-dev

# Final stage - much smaller
FROM python:3.13-slim

# Install only runtime dependencies
RUN apt update && apt install -y sqlite3 tzdata && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Set timezone
ENV TZ="America/Los_Angeles"
ENV PATH="/app/.venv/bin:$PATH"
ENV APP_ENV="preprod"

# Expose ports
EXPOSE 8000 7999

# Run the application
CMD ["sh", "-c", "\
  case \"$APP_ENV\" in \
    prod) PORT=8000 ;; \
    preprod) PORT=7999 ;; \
    *) echo \"Invalid APP_ENV=$APP_ENV\" && exit 1 ;; \
  esac && \
  python -m uvicorn api.app:app --host 0.0.0.0 --port $PORT \
"]
