# Aegis SLO & Error Budget Engine

Core Site Reliability Engineering (SRE) engine of the Aegis platform.

## Features
- **SLI Evaluation**: Connects to Prometheus to query real-time Availability, Latency (p95, p99), and Error Rates.
- **Declarative SLOs**: Evaluates targets specified in YAML (`configs/slos/*.yaml`).
- **Error Budget Accounting**: Computes remaining error budget percentages and burn rates.
- **Dual Presentation**: Colored terminal tables (`rich`) and machine-readable JSON for downstream incident automation.

## Quickstart (Local Evaluation)
```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run single evaluation against local Prometheus (port 9090)
python -m app.main --slo-config ../../configs/slos/payment-api.yaml

# 3. Run in live continuous watch mode
python -m app.main --slo-config ../../configs/slos/payment-api.yaml --watch

# 4. Output structured JSON
python -m app.main --slo-config ../../configs/slos/payment-api.yaml --json
```
