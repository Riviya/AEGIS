# Phase 3 — SLI / SLO / Error Budget Engine

**What we are building:**
The core **Aegis SRE Decision Engine** (`apps/aegis-engine`). We will:
1. Define declarative **Service Level Objectives (SLOs)** in YAML (`configs/slos/payment-api.yaml`) for Availability (99.0%), Latency p95 (<= 200ms), and Error Rate (<= 1.0%).
2. Build a Python-based SRE engine that automatically connects to the **Prometheus HTTP API**, executes PromQL queries, and extracts real-time **Service Level Indicators (SLIs)**.
3. Calculate **Remaining Error Budgets (%)** and **Burn Rates** mathematically to quantify how fast reliability is being consumed.
4. Output structured CLI tables (with progress bars and status badges) as well as machine-readable JSON for downstream automated incident detection (Phase 4).
5. Prove that when a 30% error rate is injected, Aegis detects the **SLO violation**, depletes the error budget to **0.0%**, and records a **30.0x burn rate**.

**Why:**
Raw telemetry graphs in Grafana (Phase 2) are passive — humans must sit and watch them. In modern Site Reliability Engineering (SRE), platforms must be **proactive**. Aegis needs an objective mathematical model to evaluate whether an API is meeting its reliability commitments and how quickly an ongoing failure will exhaust the allowable downtime budget before deciding to trigger automated remediation (Phase 6 & 7).

**Success gate:** [PHASE_GATES.md](PHASE_GATES.md) Phase 3:
- For a declarative YAML SLO, the Aegis engine prints SLI compliance and remaining error budget.
- Forcing an error-rate increase (`FAIL_RATE=0.30`) demonstrates an instant SLO violation, 0% remaining budget, and an accelerated burn rate.
- Re-check: Prometheus and Grafana continue to operate without disruption.

---

## 1. Core SRE Concepts (Read Before Commands)

| Concept | Definition & Academic Importance | Mathematical Formula |
| :--- | :--- | :--- |
| **SLI (Service Level Indicator)** | A quantitative measure of service behavior observed in real time. | $\text{Availability SLI} = \frac{\text{Successful Requests (non-5xx)}}{\text{Total Requests}} \times 100\%$ |
| **SLO (Service Level Objective)** | A target reliability level agreed upon by product and engineering teams over a rolling time window. | E.g., $\text{Availability} \ge 99.0\%$ over 5 minutes. |
| **SLA (Service Level Agreement)** | A legal/business contract with end-users that incurs financial or contractual penalties if breached. | SLOs are stricter internal safety buffers to prevent SLA breaches. |
| **Error Budget** | The allowable amount of unreliability a system is permitted to experience. | $\text{Total Budget} = 100\% - \text{SLO Target} = 100\% - 99.0\% = 1.0\%$ |
| **Remaining Error Budget** | The proportion of the allowable failure budget that remains unconsumed in the current window. | $\text{Remaining Budget (\%)} = \max\left(0, \frac{\text{Total Budget} - \text{Actual Error Rate}}{\text{Total Budget}} \times 100\right)$ |
| **Error Budget Burn Rate** | The rate at which the error budget is being consumed relative to the allowable rate. | $\text{Burn Rate} = \frac{\text{Actual Error Rate}}{\text{Total Budget}}$<br>• $\mathbf{1.0x}$: Budget consumed exactly as expected over window.<br>• $\mathbf{30.0x}$: Emergency! Budget will be exhausted 30 times faster. |

---

## 2. Architecture: How Phase 3 Fits into Aegis

```text
  ┌─────────────────────────────────────────────────────────────┐
  │ Kubernetes Cluster (kind: aegis)                            │
  │                                                             │
  │  [ Namespace: demo ]                                        │
  │  ┌───────────────────────────────────────────────────────┐  │
  │  │  Pod: payment-api                                     │  │
  │  │   • Exposes: /metrics                                 │  │
  │  └───────────────────────────┬───────────────────────────┘  │
  │                              │ Scraped every 5s             │
  │  [ Namespace: monitoring ]   ▼                              │
  │  ┌───────────────────────────────────────────────────────┐  │
  │  │  Prometheus (:9090)                                   │  │
  │  │   • Stores time-series data                           │  │
  │  │   • Evaluates PromQL Instant Vectors                  │  │
  │  └───────────────────────────┬───────────────────────────┘  │
  └──────────────────────────────┼──────────────────────────────┘
                                 │
            Prometheus HTTP API  │ (http://localhost:9090/api/v1/query)
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Aegis Control Plane — SLO & Error Budget Engine (apps/aegis-engine)   │
│                                                                        │
│  ┌────────────────────────┐         ┌───────────────────────────────┐  │
│  │ configs/slos/          │         │ PromQL SLI Queries            │  │
│  │ payment-api.yaml       │ ──────► │ • sum(rate(http_requests...)) │  │
│  │ (Target: 99.0% Avail,  │         │ • histogram_quantile(0.95...) │  │
│  │  p95 < 200ms)          │         └──────────────┬────────────────┘  │
│  └────────────────────────┘                        │                   │
│                                                    ▼                   │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  SRE Evaluation & Error Budget Mathematics                       │  │
│  │  • Availability SLI: 100.0%  ──► Status: MET (Healthy)           │  │
│  │  • Latency p95: 45.2 ms      ──► Status: MET (Healthy)           │  │
│  │  • Error Budget Remaining: 100.0% [████████████████████]         │  │
│  │  • Burn Rate: 0.0x (Normal)                                      │  │
│  └─────────────────────────────────┬────────────────────────────────┘  │
└────────────────────────────────────┼───────────────────────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
         [ Interactive Terminal ]           [ Structured JSON ]
          Rich Console SRE Table             Phase 4 Incident Engine
```

---

## 3. Step-by-Step Implementation Guide

### Step 3.0: Validate Phase 2 Gate (Prerequisite)

Ensure your Kubernetes cluster is running and port-forwarding to Prometheus is active.

```powershell
# What it does: Verifies all pods across namespaces are 1/1 Running.
# Why: Both payment-api (demo) and prometheus (monitoring) must be healthy.
# Expect: payment-api, wso2am, prometheus, grafana are all Running.
kubectl get pods -A
```

In a dedicated background terminal, forward Prometheus port 9090:

```powershell
# What it does: Exposes Prometheus HTTP API to your laptop on localhost:9090.
# Why: Aegis Engine queries Prometheus over HTTP.
# Keep this running in its own terminal window.
kubectl -n monitoring port-forward svc/prometheus 9090:9090
```

---

### Step 3.1: Review the Declarative SLO Policy

Inspect [configs/slos/payment-api.yaml](../configs/slos/payment-api.yaml):

```yaml
api_name: "payment-api"
service_label: "payment-api"
namespace: "demo"
evaluation_window: "5m"

slos:
  availability:
    enabled: true
    target_percent: 99.0          # Target: 99.0% of requests must succeed
    warning_threshold_percent: 99.5
    sli_query: >-
      (sum(rate(http_requests_total{app="payment-api", status!~"5.."}[{window}])) or vector(0))
      /
      (sum(rate(http_requests_total{app="payment-api"}[{window}])) > 0)
      * 100

  latency:
    enabled: true
    p95_target_ms: 200.0          # Target: p95 latency <= 200 ms
    p99_target_ms: 500.0          # Target: p99 latency <= 500 ms
    p95_sli_query: >-
      histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket{app="payment-api"}[{window}])) by (le)) * 1000
    p99_sli_query: >-
      histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket{app="payment-api"}[{window}])) by (le)) * 1000

  error_rate:
    enabled: true
    target_percent: 1.0           # Target: Error rate <= 1.0%
    sli_query: >-
      (sum(rate(http_requests_total{app="payment-api", status=~"5.."}[{window}])) or vector(0))
      /
      (sum(rate(http_requests_total{app="payment-api"}[{window}])) > 0)
      * 100

error_budget:
  burn_rate_warning_threshold: 2.0
  burn_rate_critical_threshold: 5.0
```

---

### Step 3.2: Install Dependencies & Run Automated Unit Tests

From the repository root:

```powershell
# What it does: Installs the required Python packages for Aegis Engine (pydantic, httpx, rich, pyyaml, pytest).
pip install -r apps\aegis-engine\requirements.txt
```

```powershell
# What it does: Runs unit tests with mocked Prometheus queries to verify mathematical correctness.
# Why: Validates that 100% health, degraded health, and 30% error injections compute correct budgets.
# Expect: 4 passed tests.
pytest apps\aegis-engine\tests -v
```

---

### Step 3.3: Evaluate Baseline SLO with Healthy Traffic

Generate healthy baseline traffic to produce clean Prometheus metrics:

```powershell
# What it does: Sends 100 requests with 0% error injection.
powershell -File .\scripts\generate-traffic.ps1 -Requests 100 -DelayMs 50
```

Now, run the **Aegis SLO Engine**:

```powershell
# What it does: Evaluates live Prometheus telemetry against configs/slos/payment-api.yaml.
# Expect: Status HEALTHY, Availability 100%, Remaining Budget 100%, Burn Rate 0.0x.
python -m apps.aegis-engine.app.main --slo-config configs/slos/payment-api.yaml
```

*(Alternatively, use the convenience PowerShell helper: `powershell -File .\scripts\evaluate-slo.ps1`)*

**Sample Healthy Output:**
```text
╭──────────────── AEGIS SRE CONTROL PLANE — SLO & ERROR BUDGET EVALUATION ────────────────╮
│ Target API: payment-api  |  Namespace: demo  |  Window: 5m                                │
│ Overall Compliance: [HEALTHY]                                                           │
╰─────────────────────────────────────────────────────────────────────────────────────────╯
                        Service Level Indicators (SLIs)
 ┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
 ┃ SLI Metric         ┃ Target (SLO) ┃ Current SLI ┃   Status   ┃ Assessment Note      ┃
 ┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
 │ Availability       │       99.0 % │     100.0 % │   ✓ MET    │ Target >= 99.0%      │
 │ Latency (p95)      │     200.0 ms │     35.4 ms │   ✓ MET    │ Target <= 200.0 ms   │
 │ Error Rate (5xx)   │        1.0 % │       0.0 % │   ✓ MET    │ Target <= 1.0%       │
 └────────────────────┴──────────────┴─────────────┴────────────┴──────────────────────┘
╭────────────────────────── Error Budget & Burn Rate Accounting ──────────────────────────╮
│ Total Error Budget (100% - Target)   1.0%                                               │
│ Consumed Unreliability (Error Rate)  0.0%                                               │
│ Remaining Error Budget               ████████████████████ 100.0%                        │
│ Error Budget Burn Rate               0.0x                                               │
╰─────────────────────────────────────────────────────────────────────────────────────────╯
```

---

### Step 3.4: Inject Fault & Observe SLO Violation and Error Budget Depletion

Now simulate a real backend outage by injecting a **30% failure rate** into `payment-api`:

```powershell
# What it does: Configures payment-api to fail 30% of incoming requests with HTTP 500.
kubectl -n demo set env deployment/payment-api FAIL_RATE="0.30"
```

```powershell
# What it does: Generates 150 requests to register the failure in Prometheus.
powershell -File .\scripts\generate-traffic.ps1 -Requests 150 -DelayMs 50
```

Evaluate the SLO again:

```powershell
# What it does: Runs the SLO engine against the degraded service metrics.
# Expect: Status VIOLATED, Error Rate ~30%, Remaining Budget 0.0% (EXHAUSTED), Burn Rate ~30.0x.
python -m apps.aegis-engine.app.main --slo-config configs/slos/payment-api.yaml
```

**Sample Injected Failure Output:**
```text
╭──────────────── AEGIS SRE CONTROL PLANE — SLO & ERROR BUDGET EVALUATION ────────────────╮
│ Target API: payment-api  |  Namespace: demo  |  Window: 5m                                │
│ Overall Compliance: [VIOLATED]                                                          │
╰─────────────────────────────────────────────────────────────────────────────────────────╯
                        Service Level Indicators (SLIs)
 ┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
 ┃ SLI Metric         ┃ Target (SLO) ┃ Current SLI ┃   Status   ┃ Assessment Note      ┃
 ┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
 │ Availability       │       99.0 % │      70.2 % │ ✗ VIOLATED │ Target >= 99.0%      │
 │ Latency (p95)      │     200.0 ms │     38.1 ms │   ✓ MET    │ Target <= 200.0 ms   │
 │ Error Rate (5xx)   │        1.0 % │      29.8 % │ ✗ VIOLATED │ Target <= 1.0%       │
 └────────────────────┴──────────────┴─────────────┴────────────┴──────────────────────┘
╭────────────────────────── Error Budget & Burn Rate Accounting ──────────────────────────╮
│ Total Error Budget (100% - Target)   1.0%                                               │
│ Consumed Unreliability (Error Rate)  29.8%                                              │
│ Remaining Error Budget               ░░░░░░░░░░░░░░░░░░░░ 0.0% (EXHAUSTED)              │
│ Error Budget Burn Rate               29.8x (ACCELERATED)                                │
│ Estimated Time to Exhaustion         0 min (Budget Fully Exhausted)                     │
╰─────────────────────────────────────────────────────────────────────────────────────────╯
```

---

### Step 3.5: Reset & Verify Error Budget Recovery

Restore `payment-api` back to normal:

```powershell
# What it does: Restores failure rate to 0.
kubectl -n demo set env deployment/payment-api FAIL_RATE="0"
```

Send 100 healthy requests:

```powershell
powershell -File .\scripts\generate-traffic.ps1 -Requests 100 -DelayMs 50
```

Re-run the SLO engine to verify that the latest 1-minute sliding window recovers:

```powershell
python -m apps.aegis-engine.app.main --slo-config configs/slos/payment-api.yaml --window 1m
```

---

### Step 3.6: Output Machine-Readable JSON (Phase 4 Bridge)

To see the structured payload that Phase 4 (Incident Detection) will consume:

```powershell
# What it does: Emits structured JSON telemetry.
python -m apps.aegis-engine.app.main --slo-config configs/slos/payment-api.yaml --json
```

```json
{
  "api_name": "payment-api",
  "namespace": "demo",
  "evaluation_window": "5m",
  "timestamp": "2026-08-31T18:00:00.000000+00:00",
  "overall_status": "HEALTHY",
  "slis": {
    "availability": {
      "target": 99.0,
      "actual": 100.0,
      "unit": "%",
      "is_compliant": true,
      "status": "HEALTHY",
      "details": "Target >= 99.0%"
    },
    "latency_p95": {
      "target": 200.0,
      "actual": 35.4,
      "unit": "ms",
      "is_compliant": true,
      "status": "HEALTHY",
      "details": "Target <= 200.0 ms"
    },
    "error_rate": {
      "target": 1.0,
      "actual": 0.0,
      "unit": "%",
      "is_compliant": true,
      "status": "HEALTHY",
      "details": "Target <= 1.0%"
    }
  },
  "error_budget": {
    "slo_target_percent": 99.0,
    "total_budget_percent": 1.0,
    "consumed_budget_percent": 0.0,
    "remaining_budget_percent": 100.0,
    "burn_rate": 0.0,
    "status": "HEALTHY",
    "time_to_exhaustion": null
  }
}
```

---

## 4. Key Mathematical Formulas & SRE Theory

### 1. Availability SLI Formula
$$\text{Availability SLI} = \frac{\sum \text{rate}(http\_requests\_total\{status ! \sim "5.."\} [W])}{\sum \text{rate}(http\_requests\_total[W])} \times 100$$
Where $W$ is the sliding evaluation window (e.g., $5\text{m}$).

### 2. Remaining Error Budget (%)
$$\text{Total Budget} = 100\% - \text{Target Availability}$$
$$\text{Consumed Budget} = \text{Actual Error Rate}$$
$$\text{Remaining Budget (\%)} = \max\left(0, \frac{\text{Total Budget} - \text{Consumed Budget}}{\text{Total Budget}} \times 100\right)$$

*Example Calculation:*
- Target Availability = $99.0\%$ $\implies$ Total Budget = $1.0\%$.
- If current error rate is $0.2\%$:
  $$\text{Remaining Budget} = \frac{1.0 - 0.2}{1.0} \times 100 = 80.0\%$$
- If current error rate is $30.0\%$:
  $$\text{Remaining Budget} = \max\left(0, \frac{1.0 - 30.0}{1.0} \times 100\right) = 0.0\% \quad (\text{Budget Depleted})$$

### 3. Error Budget Burn Rate
$$\text{Burn Rate} = \frac{\text{Observed Error Rate}}{\text{Total Allowable Error Budget}}$$
- $\text{Burn Rate} = 1.0$: Exactly exhausts $100\%$ of the budget over the window.
- $\text{Burn Rate} = 30.0$: Consuming the budget $30\times$ faster than permitted.

---

## 5. Troubleshooting Common Issues

1. **`ConnectionError: Could not connect to Prometheus at http://localhost:9090`:**
   - Cause: Prometheus port-forward is not active.
   - Fix: Run `kubectl -n monitoring port-forward svc/prometheus 9090:9090` in a background terminal.

2. **SLIs show `No Data`:**
   - Cause: No HTTP traffic has been sent during the sliding window (e.g., last 5 minutes).
   - Fix: Run `powershell -File .\scripts\generate-traffic.ps1 -Requests 50` to feed metrics into Prometheus.

3. **`ModuleNotFoundError: No module named 'pydantic'`:**
   - Fix: Run `pip install -r apps\aegis-engine\requirements.txt`.

---

## 6. What to Document for Your University Dissertation / Viva

- **The Philosophy of Error Budgets**: Explain why an error budget is a deliberate architectural tool that balances developer deployment velocity with system stability (Google SRE Book).
- **Multi-Metric SLIs**: Explain why measuring Availability alone is insufficient without Latency percentiles ($p95$, $p99$), as an API responding in 10 seconds is effectively down from an end-user perspective.
- **Why Burn Rates are Superior to Static Alerts**: Explain that static threshold alerts fire indiscriminately on transient blips, whereas Burn Rate alerting scales with the severity and consumption speed of the incident.
- **Evidence to Include in Chapter 4 / 5**:
  1. Terminal screenshot of the **Healthy SRE Table** (100% budget, 0.0x burn rate).
  2. Terminal screenshot of the **Violated SRE Table** under `FAIL_RATE=0.30` showing zero remaining budget and 30x burn rate.
  3. Code snippet of `apps/aegis-engine/app/slo_engine.py` demonstrating programmatic PromQL evaluation.

---

## 7. Files in this Phase (Quick Map)

| File | Purpose |
| :--- | :--- |
| `configs/slos/payment-api.yaml` | Declarative SLO contracts (Targets for Availability, Latency, Error Rate) |
| `apps/aegis-engine/app/config.py` | Pydantic schema validation for SLO YAML definitions |
| `apps/aegis-engine/app/prometheus_client.py` | HTTP client querying Prometheus `/api/v1/query` |
| `apps/aegis-engine/app/slo_engine.py` | SRE calculation engine (SLIs, Error Budgets, Burn Rates) |
| `apps/aegis-engine/app/formatter.py` | Rich terminal tables and JSON exporter |
| `apps/aegis-engine/app/main.py` | CLI entry point supporting `--slo-config`, `--watch`, `--json` |
| `apps/aegis-engine/tests/test_slo_engine.py` | Automated unit test suite with mocked Prometheus data |
| `scripts/evaluate-slo.ps1` | PowerShell one-liner script to run SLO evaluations |
