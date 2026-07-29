# Use the official Playwright Python image (includes Chromium & required OS libs)
FROM mcr.microsoft.com/playwright/python:v1.61.0-noble

# Prevent Python from writing .pyc files & buffer output (instant terminal prints)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Set default entrypoint to run your parser script
ENTRYPOINT ["python", "main.py"]