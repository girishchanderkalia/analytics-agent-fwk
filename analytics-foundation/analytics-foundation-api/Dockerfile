FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ANALYTICS_FOUNDATION_DATA_DIR=/app/data
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt && \
    adduser --system --uid 10001 --no-create-home foundation
COPY --chown=10001:10001 foundation_api /app/foundation_api
COPY --chown=10001:10001 data /app/data
USER 10001:10001
EXPOSE 8200
CMD ["python", "-m", "uvicorn", "foundation_api.app:app", "--host", "0.0.0.0", "--port", "8200"]
