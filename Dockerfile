# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for Playwright and Node.js
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Copy all project files
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN pip install playwright \
    && playwright install chromium

# Install Node.js dependencies and build Tailwind CSS
RUN npm install \
    && npm run build-css

# Expose the port the app runs on
EXPOSE 8000

# Environment variables
ENV PYTHONUNBUFFERED=1

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]