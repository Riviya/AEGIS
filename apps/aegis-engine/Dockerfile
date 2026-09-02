FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

ENV PYTHONUNBUFFERED=1
ENV PROMETHEUS_URL=http://prometheus.monitoring.svc.cluster.local:9090

ENTRYPOINT ["python", "-m", "app.main"]
CMD ["--slo-config", "/configs/slos/payment-api.yaml", "--watch"]
