FROM python:3.13-slim

# Install system dependencies
RUN apt update && apt install -y sqlite3 vim curl tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Install uv globally and make it available in the PATH for all users
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh

# Copy only the dependency files first to leverage Docker's layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies using uv sync for reproducible builds
# Note: we use --no-dev for production
RUN uv sync --no-cache --no-dev

# Copy the rest of your application code (including admin_ui)
COPY . .

# Set the timezone
ENV TZ="America/Los_Angeles"

# Expose the API port
EXPOSE 8000

# Command to run the application using uv run and uvicorn
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
