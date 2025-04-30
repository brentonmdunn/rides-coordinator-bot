# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app,
# except the files/folders mentioned in the .dockerignore
COPY . /app

# Install any required Python packages
# If you have a requirements.txt, include it here
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# RUN pip install --no-cache-dir --index-url https://pypi.org/simple -r requirements.txt

# Specify the command to run your app
CMD ["python", "main.py"]