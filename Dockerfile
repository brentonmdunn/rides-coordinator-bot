# Use a slim Python base image
FROM python:3.13-slim

# Install system dependencies if needed (optional)
# RUN apt-get update && apt-get install -y some-package && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Install uv, the fast Python package installer
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Copy only the dependency files first to leverage Docker's layer caching
COPY pyproject.toml uv.lock ./
# If you are still using requirements.txt, use this line instead:
# COPY requirements.txt ./

# Install dependencies using uv sync for reproducible builds
# --system tells uv to install into the global Python environment
RUN uv sync --system --no-cache

# If you are still using requirements.txt, use this line instead:
# RUN uv pip install --system --no-cache -r requirements.txt

# Copy the rest of your application code
COPY . .

# Set the timezone
ENV TZ="America/Los_Angeles"

# Command to run the application
CMD ["python", "main.py"]