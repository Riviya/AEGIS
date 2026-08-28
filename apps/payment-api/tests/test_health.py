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
