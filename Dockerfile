FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application files
COPY bot.py .
COPY concat.py .
COPY request.py .
COPY knowledge-base.txt .

# Copy the test directory
COPY tests/ tests/

# Create necessary directories
RUN mkdir -p sources responses knowledge-base

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

# Run the bot
CMD ["python", "bot.py"]