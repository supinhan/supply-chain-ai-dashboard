FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY backend_api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend_api /app/backend_api
COPY ai_algorithms/supplychain-ai-service/model /app/ai_algorithms/supplychain-ai-service/model

EXPOSE 8000

CMD ["uvicorn", "backend_api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
