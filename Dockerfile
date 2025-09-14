FROM python:3.13-slim

# Install system dependencies
RUN apt update && apt install -y sqlite3 vim curl tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy only the dependency files first to leverage Docker's layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies using uv sync for reproducible builds
RUN uv sync --no-cache --no-dev

# Copy the rest of your application code
COPY . .

# Set the timezone
ENV TZ="America/Los_Angeles"

# Command to run the application
CMD ["uv", "run", "python", "main.py"]