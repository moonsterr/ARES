FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source as a proper package at /app/backend/
COPY . ./backend/

# Create data directories and download fasttext language detection model
RUN mkdir -p backend/data/models && \
    wget -q -O backend/data/models/lid.176.bin \
    https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin

EXPOSE 8000

# Run as a package so relative imports (from .database import ...) resolve correctly
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
