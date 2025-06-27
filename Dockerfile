# Use Python 3.10 slim as base image
FROM python:3.10-slim

# Set noninteractive installation to avoid prompts
ENV DEBIAN_FRONTEND=noninteractive

# System dependencies for Playwright and PostgreSQL
RUN apt-get update && apt-get install -y \
    wget curl unzip fonts-liberation \
    libasound2 libatk-bridge2.0-0 libatk1.0-0 \
    libcups2 libdbus-1-3 libgdk-pixbuf2.0-0 \
    libnspr4 libnss3 libx11-xcb1 libxcomposite1 \
    libxdamage1 libxrandr2 xdg-utils \
    libpq-dev \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Install Playwright dependencies
RUN pip install --upgrade pip && \
    pip install playwright && \
    playwright install --with-deps

# Set working directory
WORKDIR /app

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Ensure the script is executable and set environment variables
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.local/bin:$PATH"

# Command to run the application
CMD ["python", "main.py"]
