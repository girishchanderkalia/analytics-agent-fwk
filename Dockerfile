FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/agent-runtime

WORKDIR /app

RUN addgroup --system runtime && \
    adduser --system --ingroup runtime --home /nonexistent runtime && \
    mkdir -p /app/runtime-data && \
    chown -R runtime:runtime /app

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt

COPY agent-runtime /app/agent-runtime
COPY agents /app/agents

USER runtime

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
