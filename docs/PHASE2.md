# Phase 2 — Observability (Prometheus, Grafana & RED Metrics)

**What we are building:**
A lightweight, production-grade observability stack for the Aegis platform. We will:
1. Instrument `payment-api` with standard Prometheus metrics (`/metrics`) to export real-time HTTP request counts, error codes, and latency histograms.
2. Deploy a single-replica **Prometheus** server in a dedicated `monitoring` namespace to automatically scrape metrics from the API and Kubernetes.
3. Deploy **Grafana** with automated provisioning (datasource and an SRE dashboard pre-loaded) to visualize the **RED metrics** (Rate, Errors, Duration) alongside pod CPU and memory consumption.
4. Provide a PowerShell traffic generator (`generate-traffic.ps1`) to simulate normal traffic and error injection so you can see live telemetry graphs.

**Why:**
Aegis is an autonomous SRE platform. Before Aegis can detect anomalies (Phase 4), evaluate SLOs and error budgets (Phase 3), or execute automated rollbacks (Phase 6), it must be able to **observe** the system with precise, quantitative time-series data.

**Success gate:** [PHASE_GATES.md](PHASE_GATES.md) Phase 2:
- Prometheus targets show `payment-api` in `UP` state (1/1).
- Grafana dashboard displays real Request Rate (RPS), Error Rate (%), Latency percentiles (p50, p95, p99), and Pod Resource usage driven by live traffic.
- Re-check: WSO2 Gateway routing and Phase 1 payment endpoints still operate normally.

---

## 1. Core Concepts (Read Before Commands)

| Concept | Meaning & Why It Matters in Aegis |
| :--- | :--- |
| **RED Method** | The standard SRE monitoring philosophy for request-driven services:<br>• **Rate**: Requests served per second (RPS).<br>• **Errors**: Number of failing requests (HTTP 5xx).<br>• **Duration**: How long requests take (latency distribution). |
| **Pull vs. Push Model** | Prometheus uses a **pull (scraping)** model. Every few seconds (e.g., 5s), Prometheus makes an HTTP GET request to `http://payment-api:8080/metrics` and stores the numerical time-series in its local time-series database (TSDB). |
| **Metric Types** | • **Counter**: Monotonically increasing number (e.g., `http_requests_total`). Used with `rate()` to calculate per-second velocity.<br>• **Histogram**: Samples observations into configurable buckets to accurately calculate percentiles (e.g., p95, p99 latency) without taking crude averages.<br>• **Gauge**: Value that goes up and down (e.g., memory usage, active requests). |
| **PromQL** | Prometheus Query Language. Used by Grafana and Aegis engines to query metrics. Example: `sum(rate(http_requests_total[1m]))`. |
| **Grafana Provisioning** | Defining datasources and dashboards as YAML/JSON configuration files rather than clicking around in the UI. This adheres to GitOps / Infrastructure-as-Code principles. |

---

## 2. Architecture: How Phase 2 Fits into Aegis

```text
       [ Clients / Traffic Generator ]
                     │
                     ▼
          [ WSO2 API Gateway: 8243 ]
                     │
                     ▼ (In-cluster DNS)
  ┌─────────────────────────────────────────────────────────────┐
  │ Kubernetes Cluster (kind: aegis)                            │
  │                                                             │
  │  [ Namespace: demo ]                                        │
  │  ┌───────────────────────────────────────────────────────┐  │
  │  │  Pod: payment-api                                     │  │
  │  │   • Business API (:8080/payments)                     │  │
  │  │   • Prometheus Exporter (:8080/metrics) ◄──────────┐  │  │
  │  │      - http_requests_total                         │  │  │
  │  │      - http_request_duration_seconds_bucket        │  │  │
  │  │      - process_cpu_seconds_total                   │  │  │
  │  │      - process_resident_memory_bytes               │  │  │
  │  └───────────────────────────────────────────────────────┘  │
  │                                                               │
  │  [ Namespace: monitoring ]                                   │
  │  ┌────────────────────────┐       ┌──────────────────────┐  │
  │  │  Prometheus (:9090)    │ ────► │  Grafana (:3000)     │  │
  │  │  • Scrapes /metrics    │       │  • Auto-provisioned  │  │
  │  │  • 5s scrape interval  │       │  • RED Dashboard     │  │
  │  │  • In-memory TSDB      │       │  • Resource Graphs   │  │
  │  └────────────────────────┘       └──────────┬───────────┘  │
  └──────────────────────────────────────────────┼──────────────┘
                                                 │
                          kubectl port-forward   ▼
                                         [ Browser ]
                                   http://localhost:3000
```

---

## 3. Step-by-Step Implementation Guide

### Step 3.0: Validate Phase 1 Gate (Prerequisite)

Before introducing monitoring, verify that your Phase 1 components are running.

```powershell
# What it does: Checks the status of payment-api and WSO2 pods.
# Why: We must ensure the base cluster is healthy.
# Expect: payment-api is 1/1 Running, wso2am is 1/1 Running.
kubectl get pods -A
```

```powershell
# What it does: Calls the direct health endpoint on payment-api.
# Expect: {"status":"ok","service":"payment-api"}
curl.exe http://localhost:18080/health
```

---

### Step 3.1: Instrument `payment-api` with Prometheus Metrics

We update `apps/payment-api/requirements.txt` to include `prometheus-fastapi-instrumentator` and modify `apps/payment-api/app/main.py`.

#### 1. Update `apps/payment-api/requirements.txt`:
```text
fastapi==0.115.12
uvicorn[standard]==0.34.2
httpx==0.28.1
pytest==8.3.5
prometheus-fastapi-instrumentator==7.0.0
```

#### 2. Update `apps/payment-api/app/main.py`:
```python
"""Sample backend API that Aegis will protect.

Instrumented with Prometheus metrics for Phase 2 Observability.
"""

from __future__ import annotations

import os
import random
from typing import Any

from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(
    title="payment-api",
    version="0.1.0",
    description="Phase 2 sample API for Aegis with Prometheus Observability.",
)

# Instrument the FastAPI application with Prometheus exporter
instrumentator = Instrumentator(
    should_group_status_codes=False,
    should_ignore_untemplated=True,
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/health", "/metrics"],
    inprogress_name="http_requests_in_progress",
    inprogress_labels=True,
)
instrumentator.instrument(app).expose(app, endpoint="/metrics")


def _fail_rate() -> float:
    """Fraction of /payments requests that should fail (0.0 to 1.0)."""
    raw = os.getenv("FAIL_RATE", "0")
    try:
        value = float(raw)
    except ValueError:
        return 0.0
    return min(max(value, 0.0), 1.0)


@app.get("/health")
def health() -> dict[str, str]:
    """Kubernetes liveness/readiness probe. Excluded from business metrics."""
    return {"status": "ok", "service": "payment-api"}


@app.get("/payments")
def list_payments() -> dict[str, Any]:
    """Business endpoint. Returns payment records or injected failure."""
    if random.random() < _fail_rate():
        raise HTTPException(status_code=500, detail="injected failure")
    return {
        "items": [
            {"id": "pay-001", "amount": 12.50, "currency": "USD", "status": "settled"},
            {"id": "pay-002", "amount": 3.00, "currency": "USD", "status": "pending"},
        ]
    }


@app.get("/payments/{payment_id}")
def get_payment(payment_id: str) -> dict[str, Any]:
    if random.random() < _fail_rate():
        raise HTTPException(status_code=500, detail="injected failure")
    if payment_id not in {"pay-001", "pay-002"}:
        raise HTTPException(status_code=404, detail="payment not found")
    return {"id": payment_id, "amount": 12.50, "currency": "USD", "status": "settled"}
```

#### 3. Update `apps/payment-api/tests/test_health.py`:
Add a test ensuring `/metrics` is reachable:
```python
def test_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text or "process_cpu_seconds_total" in response.text
```

---

### Step 3.2: Rebuild & Reload `payment-api:0.2.0` into kind

```powershell
# What it does: Builds the new image with Prometheus metrics support.
# Why: Kubernetes needs the updated image containing the instrumented code.
# Expect: "naming to docker.io/library/payment-api:0.2.0"
docker build -t payment-api:0.2.0 apps\payment-api
```

```powershell
# What it does: Loads the image directly into the kind node container.
# Why: kind cannot access your Windows local Docker daemon directly.
# Expect: Image loaded successfully into kind cluster "aegis".
kind load docker-image payment-api:0.2.0 --name aegis
```

```powershell
# What it does: Updates the Deployment image to payment-api:0.2.0.
# Why: Triggers a zero-downtime rolling update in Kubernetes.
# Expect: "deployment.apps/payment-api image updated"
kubectl -n demo set image deployment/payment-api payment-api=payment-api:0.2.0
```

```powershell
# What it does: Waits for the rolling restart to finish.
# Expect: deployment "payment-api" successfully rolled out.
kubectl -n demo rollout status deployment/payment-api --timeout=60s
```

```powershell
# What it does: Verifies the metrics endpoint directly from your terminal.
# Expect: A text stream containing Prometheus metric definitions (# HELP, # TYPE).
curl.exe http://localhost:18080/metrics
```

---

### Step 3.3: Deploy Prometheus in Kubernetes

We create the `monitoring` namespace and deploy Prometheus configured to scrape `payment-api` every 5 seconds.

#### Manifests to apply:
1. `infra/k8s/monitoring/namespace.yaml`
2. `infra/k8s/monitoring/prometheus-rbac.yaml`
3. `infra/k8s/monitoring/prometheus-config.yaml`
4. `infra/k8s/monitoring/prometheus-deployment.yaml`

```powershell
# What it does: Creates the monitoring namespace and Prometheus RBAC roles.
# Why: Allows Prometheus to discover services and nodes in the cluster.
kubectl apply -f infra\k8s\monitoring\namespace.yaml
kubectl apply -f infra\k8s\monitoring\prometheus-rbac.yaml
```

```powershell
# What it does: Creates the Prometheus configuration ConfigMap.
# Why: Defines scrape targets (payment-api:8080/metrics).
kubectl apply -f infra\k8s\monitoring\prometheus-config.yaml
```

```powershell
# What it does: Deploys Prometheus Server and exposes it via a Service.
# Expect: Prometheus pod starts.
kubectl apply -f infra\k8s\monitoring\prometheus-deployment.yaml
```

```powershell
# What it does: Waits for Prometheus to become Ready.
# Expect: deployment "prometheus" successfully rolled out.
kubectl -n monitoring rollout status deployment/prometheus --timeout=90s
```

---

### Step 3.4: Deploy Grafana with Auto-Provisioning

We deploy Grafana pre-configured with:
- **Datasource**: Automatically points to `http://prometheus.monitoring.svc.cluster.local:9090`.
- **Dashboard Provider**: Automatically loads the **Aegis SRE Dashboard** without requiring manual JSON imports.

```powershell
# What it does: Applies Grafana datasource and dashboard provisioning ConfigMaps.
kubectl apply -f infra\k8s\monitoring\grafana-datasources.yaml
kubectl apply -f infra\k8s\monitoring\grafana-dashboards-provider.yaml
kubectl apply -f infra\k8s\monitoring\grafana-dashboard-aegis.yaml
```

```powershell
# What it does: Deploys Grafana server.
kubectl apply -f infra\k8s\monitoring\grafana-deployment.yaml
```

```powershell
# What it does: Waits for Grafana to become Ready.
# Expect: deployment "grafana" successfully rolled out.
kubectl -n monitoring rollout status deployment/grafana --timeout=90s
```

---

## 4. Verification & Testing Guide

### 4.1 Access the UIs

Open two separate PowerShell windows to forward the ports (or run in background):

```powershell
# Forward Grafana (Port 3000)
# Open browser at: http://localhost:3000 (Default login: admin / admin)
kubectl -n monitoring port-forward svc/grafana 3000:3000
```

```powershell
# (Optional) Forward Prometheus (Port 9090)
# Open browser at: http://localhost:9090/targets
kubectl -n monitoring port-forward svc/prometheus 9090:9090
```

1. Open **[http://localhost:9090/targets](http://localhost:9090/targets)** in your browser:
   - Check that `payment-api` target is **UP (1/1)**.
2. Open **[http://localhost:3000](http://localhost:3000)** in your browser:
   - Log in with `admin` / `admin`.
   - Go to **Dashboards** → Open **"Aegis — API Reliability & SRE Overview"**.

---

### 4.2 Generate Live Traffic (Healthy vs. Injected Errors)

Run the traffic generation script from the repo root:

```powershell
# What it does: Sends 100 requests (healthy traffic, 0% failure rate).
# Why: Produces clean baseline telemetry for Rate, Latency, CPU, Memory.
powershell -File .\scripts\generate-traffic.ps1 -Requests 100 -DelayMs 50
```

Now inject a 30% failure rate to simulate an incident and see the **Error Rate (%)** panel turn red:

```powershell
# What it does: Injects FAIL_RATE=0.30 environment variable into payment-api.
# Why: Simulates backend partial failure.
kubectl -n demo set env deployment/payment-api FAIL_RATE="0.30"
```

```powershell
# What it does: Sends 150 requests through the API.
# Why: Generates HTTP 500 errors so you can observe the error rate spike in Grafana.
powershell -File .\scripts\generate-traffic.ps1 -Requests 150 -DelayMs 50
```

Reset failure rate back to normal:

```powershell
# What it does: Restores FAIL_RATE to 0.
kubectl -n demo set env deployment/payment-api FAIL_RATE="0"
```

---

## 5. Key PromQL Queries Explained

These are the exact queries powering the Aegis SRE Dashboard:

| Metric Panel | PromQL Expression | Explanation |
| :--- | :--- | :--- |
| **Request Rate (RPS)** | `sum(rate(http_requests_total{app="payment-api"}[1m]))` | Calculates the per-second rate of incoming HTTP requests over a 1-minute sliding window. |
| **Error Rate (%)** | `(sum(rate(http_requests_total{app="payment-api", status=~"5.."}[1m])) / sum(rate(http_requests_total{app="payment-api"}[1m]))) * 100` | Divides 5xx failing requests by total requests and multiplies by 100 to yield the exact percentage. |
| **p95 Latency** | `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{app="payment-api"}[1m])) by (le))` | Calculates the 95th percentile latency (95% of users experience response time lower than this value). |
| **p99 Latency** | `histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{app="payment-api"}[1m])) by (le))` | Calculates the 99th percentile tail latency. |
| **Process CPU Usage** | `rate(process_cpu_seconds_total{app="payment-api"}[1m]) * 100` | CPU utilization percentage of the Python process. |
| **Resident Memory** | `process_resident_memory_bytes{app="payment-api"} / (1024 * 1024)` | Physical RAM (RSS) consumed by the API pod in Megabytes (MB). |

---

## 6. Troubleshooting Common Issues

1. **Prometheus Target is `DOWN` (Connection Refused / 404):**
   - Diagnose: `kubectl -n demo get pods -o wide` and verify `payment-api` is running.
   - Run: `kubectl -n demo port-forward svc/payment-api 8080:8080` and test `curl.exe http://localhost:8080/metrics`.
   - Check scrape config in `infra/k8s/monitoring/prometheus-config.yaml`: ensure `payment-api.demo.svc.cluster.local:8080` is the exact hostname.

2. **Grafana Panels Show `No Data`:**
   - In Grafana, check **Connections → Data Sources → Prometheus → Save & Test**. It should return `Successfully queried the Prometheus API`.
   - Ensure you ran `generate-traffic.ps1` — Prometheus rate queries require at least 2 data points over the scrape interval to calculate rates.

3. **High Memory / OOMKilled:**
   - Prometheus and Grafana are capped at `256Mi` and `512Mi` limits respectively to protect your laptop RAM. If Docker Desktop runs low on memory, reduce Prometheus retention in `prometheus-deployment.yaml` (`--storage.tsdb.retention.time=2h`).

---

## 7. What to Document for Your University Dissertation / Viva

- **Architectural Diagram**: Show the decoupled pull-based metrics pipeline (API Exporter → Prometheus Scraper → Grafana Engine).
- **The 4 Golden Signals**: Explain why SRE relies on RED metrics (Rate, Errors, Duration) rather than just host CPU/RAM to measure user-facing reliability.
- **Histogram Quantiles vs. Averages**: Explain mathematically why average latency masks tail latency anomalies and why `histogram_quantile()` is mandatory for SLO definitions.
- **Evidence Screenshots**:
  1. Prometheus target discovery screen showing `payment-api` healthy.
  2. Grafana dashboard showing normal traffic (0% error rate, stable p95).
  3. Grafana dashboard showing the spike when `FAIL_RATE=0.30` was injected.

---

## 8. What to Measure Later (Phase 3 & 4 Linkage)

In Phase 3, we will write the **Aegis SLO Engine** in Python, which will programmatically query these exact PromQL expressions to calculate:
- **SLI Availability**: $100 - \text{Error Rate}$
- **Error Budget Consumption Rate**: How fast the allowable 0.1% budget is burning during an incident.
