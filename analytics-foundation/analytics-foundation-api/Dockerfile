FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY foundation_api ./foundation_api
COPY data ./data
ENV ANALYTICS_FOUNDATION_DATA_DIR=/app/data
EXPOSE 8200
CMD ["uvicorn", "foundation_api.app:app", "--host", "0.0.0.0", "--port", "8200"]
