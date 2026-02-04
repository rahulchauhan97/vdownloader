FROM python:3.11-slim

# Install ffmpeg for video processing
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY main.py .
COPY data/ ./data/

# Create directories for downloads
RUN mkdir -p /app/downloads /app/temp

# Set Datadog environment variables (can be overridden)
ENV DD_SERVICE=vdownloader
ENV DD_ENV=production
ENV DD_VERSION=1.0.0

# Run the bot
CMD ["ddtrace-run", "python", "main.py"]
