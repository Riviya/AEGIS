"""Sample backend API that Aegis will protect.

This service is intentionally small. WSO2 API Manager sits in front of it.
Later phases can force failures with FAIL_RATE without rewriting the app.
"""

from __future__ import annotations

import os
import random
from typing import Any

from fastapi import FastAPI, HTTPException

app = FastAPI(
    title="payment-api",
    version="0.1.0",
    description="Phase 1 sample API for Aegis (WSO2 + Kubernetes).",
)


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
    """Kubernetes liveness/readiness probe. Keep this cheap and always 200 unless the process is dying."""
    return {"status": "ok", "service": "payment-api"}


@app.get("/payments")
def list_payments() -> dict[str, Any]:
    """Business endpoint. Clients should call this through the WSO2 gateway, not the Service directly."""
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
