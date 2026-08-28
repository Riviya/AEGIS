# Small runtime image for payment-api.
# Build: docker build -t payment-api:0.1.0 apps/payment-api
# Why python:3.12-slim: enough for FastAPI, smaller than a full Python image.

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FAIL_RATE=0

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Container listens on 8080 so the Kubernetes Service can target a fixed port.
EXPOSE 8080

# --host 0.0.0.0: accept traffic from other pods (WSO2 gateway), not only localhost.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
