FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including ffmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Run with gunicorn - PORT is set at runtime by Railway
CMD ["/bin/bash", "-c", "gunicorn app:app --bind 0.0.0.0:$PORT --timeout 600 --workers 1"]
