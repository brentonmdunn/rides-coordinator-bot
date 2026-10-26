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

# Install Doppler from its signed Debian repository (secrets are fetched only at runtime).
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl gnupg && \
    curl -sLf --retry 3 --tlsv1.2 --proto "=https" https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key \
      | gpg --dearmor -o /usr/share/keyrings/doppler-archive-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/doppler-archive-keyring.gpg] https://packages.doppler.com/public/cli/deb/debian any-version main" \
      > /etc/apt/sources.list.d/doppler-cli.list && \
    apt-get update && apt-get install -y --no-install-recommends doppler && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

ENV PATH="/app/.venv/bin:$PATH"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
COPY doppler-entrypoint.sh /doppler-entrypoint.sh
RUN chmod +x /doppler-entrypoint.sh
ENTRYPOINT ["/doppler-entrypoint.sh"]

# Expose port
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
