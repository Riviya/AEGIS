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
    version="0.2.0",
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
