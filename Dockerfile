FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MMVS_DATA_ROOT=/app/VIDEO_SYSTEM

WORKDIR /app/VIDEO_SYSTEM

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY video_registry.json .
COPY registry_schema.md .
COPY README.md .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
