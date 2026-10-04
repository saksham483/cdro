FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code and frontend static assets
COPY backend/ /app/
COPY frontend/ /app/frontend/

ENV PORT=5000
ENV PYTHONPATH=/app
EXPOSE 5000

CMD ["python", "run.py"]
