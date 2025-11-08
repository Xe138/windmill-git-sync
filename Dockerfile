FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install wmill CLI
RUN curl -L https://github.com/windmill-labs/windmill/releases/latest/download/wmill-linux-amd64 -o /usr/local/bin/wmill \
    && chmod +x /usr/local/bin/wmill

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create workspace directory
RUN mkdir -p /workspace

# Expose port for webhook server
EXPOSE 8080

# Run the Flask server
CMD ["python", "-u", "app/server.py"]
