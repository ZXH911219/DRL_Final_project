# Base image with Python and PyTorch
FROM pytorch/pytorch:2.0.1-cuda11.7-runtime-ubuntu22.04

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    tesseract-ocr \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src /app/src
COPY main.py /app/
COPY configs /app/configs

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/models

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start command
CMD ["uvicorn", "src.core.api:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
