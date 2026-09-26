import time
import uuid

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

HEADERS = {
    "X-API-Key": "minipay-key"
}


def unique():
    return uuid.uuid4().hex[:10]


def create_customer():
    response = client.post(
        "/api/customers",
        headers=HEADERS,
        json={
            "customer_ref": "C-" + unique(),
            "name": "Test Customer"
        }
    )

    assert response.status_code == 201

    return response.json()["id"]


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_customer():
    response = client.post(
        "/api/customers",
        headers=HEADERS,
        json={
            "customer_ref": "C-" + unique(),
            "name": "Ali"
        }
    )

    assert response.status_code == 201

    data = response.json()

    assert "id" in data
    assert "customer_ref" in data
    assert "name" in data
    assert "created_at" in data


def test_missing_customer_field():
    response = client.post(
        "/api/customers",
        headers=HEADERS,
        json={
            "customer_ref": "C-" + unique()
        }
    )

    assert response.status_code == 422


def test_authentication():
    response = client.post(
        "/api/customers",
        json={
            "customer_ref": "C-" + unique(),
            "name": "Ali"
        }
    )

    assert response.status_code == 401


def test_duplicate_customer():
    ref = "C-" + unique()

    body = {
        "customer_ref": ref,
        "name": "Ali"
    }

    first = client.post(
        "/api/customers",
        headers=HEADERS,
        json=body
    )

    assert first.status_code == 201

    second = client.post(
        "/api/customers",
        headers=HEADERS,
        json=body
    )

    assert second.status_code == 409


def test_create_payment():
    customer_id = create_customer()

    response = client.post(
        "/api/payments",
        headers=HEADERS,
        json={
            "transaction_ref": "T-" + unique(),
            "customer_id": customer_id,
            "amount": 100.50
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert "id" in data
    assert data["customer_id"] == customer_id
    assert data["amount"] == 100.50
    assert data["status"] == "SUCCESS"


def test_invalid_payment_amount():
    customer_id = create_customer()

    response = client.post(
        "/api/payments",
        headers=HEADERS,
        json={
            "transaction_ref": "T-" + unique(),
            "customer_id": customer_id,
            "amount": -10
        }
    )

    assert response.status_code == 422


def test_unknown_customer():
    response = client.post(
        "/api/payments",
        headers=HEADERS,
        json={
            "transaction_ref": "T-" + unique(),
            "customer_id": 999999999,
            "amount": 100
        }
    )

    assert response.status_code == 404


def test_idempotent_payment():
    customer_id = create_customer()

    ref = "T-" + unique()

    body = {
        "transaction_ref": ref,
        "customer_id": customer_id,
        "amount": 500
    }

    first = client.post(
        "/api/payments",
        headers=HEADERS,
        json=body
    )

    assert first.status_code == 200

    first_data = first.json()

    second = client.post(
        "/api/payments",
        headers=HEADERS,
        json=body
    )

    assert second.status_code == 200

    second_data = second.json()

    assert first_data["id"] == second_data["id"]


def test_payment_lookup():
    customer_id = create_customer()

    response = client.post(
        "/api/payments",
        headers=HEADERS,
        json={
            "transaction_ref": "T-" + unique(),
            "customer_id": customer_id,
            "amount": 250
        }
    )

    payment_id = response.json()["id"]

    response = client.get(
        f"/api/payments/{payment_id}",
        headers=HEADERS
    )

    assert response.status_code == 200
    assert response.json()["id"] == payment_id


def test_unknown_payment():
    response = client.get(
        "/api/payments/999999999",
        headers=HEADERS
    )

    assert response.status_code == 404


def test_customer_payments():
    customer_id = create_customer()

    client.post(
        "/api/payments",
        headers=HEADERS,
        json={
            "transaction_ref": "T-" + unique(),
            "customer_id": customer_id,
            "amount": 100
        }
    )

    response = client.get(
        f"/api/customers/{customer_id}/payments",
        headers=HEADERS
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1


def test_response_content_type():
    response = client.get("/health")

    assert response.headers["content-type"].startswith(
        "application/json"
    )


def test_response_time():
    start = time.perf_counter()

    response = client.get("/health")

    elapsed = time.perf_counter() - start

    assert response.status_code == 200
    assert elapsed < 0.5