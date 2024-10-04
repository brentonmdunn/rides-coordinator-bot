# Use Python 
FROM --platform=linux/amd64 python:latest

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all Python files into the container
COPY *.py /app/

# Run the main.py script when the container starts
CMD ["python3", "main.py"]

