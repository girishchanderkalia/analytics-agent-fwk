FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY analytics-foundation/analytics-foundation-client /app/packages/analytics-foundation-client
COPY analytics-foundation/analytics-foundation-mcp /app/packages/analytics-foundation-mcp
RUN python -m pip install --no-cache-dir \
      /app/packages/analytics-foundation-client \
      /app/packages/analytics-foundation-mcp && \
    adduser --system --uid 10001 --no-create-home foundation-mcp

USER 10001:10001
EXPOSE 8300
CMD ["python", "-m", "uvicorn", "analytics_foundation_mcp.app:app", "--host", "0.0.0.0", "--port", "8300"]
