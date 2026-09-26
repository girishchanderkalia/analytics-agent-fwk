FROM python:3.13-slim
WORKDIR /workspace
COPY opo-deterministic-logic /workspace/opo-deterministic-logic
COPY opo-capability-service /workspace/opo-capability-service
RUN python -m pip install --no-cache-dir /workspace/opo-deterministic-logic /workspace/opo-capability-service
USER 10001
EXPOSE 8300
CMD ["python", "-m", "uvicorn", "opo_capability_service.app:app", "--host", "0.0.0.0", "--port", "8300"]
