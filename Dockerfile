FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/agent-runtime \
    AGENT_APPLICATION_ID=opo-monitoring \
    AGENT_MARKDOWN_PACKAGES=/app/agents/opo-monitoring \
    AGENT_RUNTIME_DATABASE_PATH=/app/runtime-data/conversations.sqlite

WORKDIR /app

RUN addgroup --system runtime && \
    adduser --system --ingroup runtime --home /nonexistent runtime && \
    mkdir -p /app/runtime-data && \
    chown -R runtime:runtime /app

COPY agent-framework/agent-runtime/requirements.txt agent-framework/agent-runtime/requirements-langgraph.txt /app/
RUN python -m pip install --no-cache-dir -r /app/requirements.txt -r /app/requirements-langgraph.txt

COPY agent-framework/agent-runtime /app/agent-runtime
COPY foundation /app/foundation
COPY agents /app/agents

USER runtime

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "runtime_api.langgraph_main:app", "--host", "0.0.0.0", "--port", "8000"]
