from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "payment-api"


def test_list_payments_ok():
    response = client.get("/payments")
    assert response.status_code == 200
    assert "items" in response.json()
    assert len(response.json()["items"]) == 2


def test_metrics_endpoint_ok():
    # Make a dummy request to trigger metric creation
    client.get("/payments")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests" in response.text or "process_cpu" in response.text
