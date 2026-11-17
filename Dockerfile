FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    TABPFN_NO_BROWSER=1 TABPFN_MODEL_CACHE_DIR=/tmp/tabpfn HF_HOME=/tmp/hf \
    ARTIFACT_DIR=/app/artifacts

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app

# CPU-only torch first, so the much larger CUDA build is not pulled in by tabpfn.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend backend
COPY ml/src/explain_agnostic.py ml/src/explain_agnostic.py
COPY ml/artifacts artifacts

# The TabPFN token is NOT in the image: Cloud Run injects TABPFN_TOKEN from Secret Manager at start-up.
CMD exec uvicorn main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8080}
