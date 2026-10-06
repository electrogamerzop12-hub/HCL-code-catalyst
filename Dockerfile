# ===============================================================================
# Production Dockerfile - University Student Services Data Ingestion Pipeline
# ===============================================================================

# 1. Use official Python 3.11 slim base image for lightweight container size
FROM python:3.11-slim

# 2. Configure environment variables for unbuffered logging and default paths
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/app/data \
    SQLITE_DB_PATH=/app/data/university.db \
    CHROMADB_DIR=/app/data/chromadb

# 3. Install required system packages (build tools and curl for container healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 4. Set working directory inside container
WORKDIR /app

# 5. Copy python dependencies list first for Docker build caching
COPY requirements.txt .

# 6. Install CPU-only version of PyTorch first (180MB instead of 2.5GB CUDA default)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 7. Install remaining application dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 8. Pre-download HuggingFace sentence-transformers model during build phase
#    This caches weights inside the Docker image so runtime requires zero internet downloads.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# 9. Copy application source code and UI into container
COPY app/ /app/app/
COPY ui/ /app/ui/
COPY scripts/ /app/scripts/

# 10. Create persistent data volume directory with full read/write permissions
RUN mkdir -p /app/data && chmod -R 777 /app/data

# 11. Expose FastAPI application port
EXPOSE 8000

# 12. Command to run production Uvicorn server on port 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
