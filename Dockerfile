FROM python:3.13-slim

# Install sqlite3 and vim
RUN apt update && apt install -y sqlite3 vim && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app,
# except the files/folders mentioned in the .dockerignore
COPY . /app

# Install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

ENV TZ="America/Los_Angeles"

CMD ["python", "main.py"]
