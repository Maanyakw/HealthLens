# HealthLens API image. Build from the project root:
#   docker build -t healthlens-api .
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 MPLBACKEND=Agg
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Only what the API needs: code + trained model files
COPY backend backend
COPY ml/src ml/src
COPY ml/models ml/models

# Cloud Run sets $PORT (default 8080)
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
