FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Node.js
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install wmill CLI via npm
RUN npm install -g windmill-cli

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
