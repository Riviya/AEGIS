# payment-api

Sample FastAPI service for Aegis Phase 1.

- `GET /health` — probe used by Kubernetes
- `GET /payments` — business data (call this **through WSO2** in demos)
- `FAIL_RATE` — `0` to `1`, used later to inject errors

Local run (without Docker):

```text
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080
```
