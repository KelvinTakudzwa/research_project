FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies (required for some Python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy ML API source and models
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Start Uvicorn
CMD ["uvicorn", "ml_api:app", "--host", "0.0.0.0", "--port", "8000"]
