import os
from datetime import datetime
from decimal import Decimal

import psycopg2
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="MiniPay API")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://minipay:minipay@localhost:5432/minipay"
)

API_KEY = os.getenv("API_KEY", "minipay-key")


def get_db():
    return psycopg2.connect(DATABASE_URL)


def check_auth(x_api_key: str | None):
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )


class CustomerCreate(BaseModel):
    customer_ref: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)


class PaymentCreate(BaseModel):
    transaction_ref: str = Field(min_length=1, max_length=50)
    customer_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/customers", status_code=201)
def create_customer(
    data: CustomerCreate,
    x_api_key: str | None = Header(None)
):
    check_auth(x_api_key)

    db = get_db()

    try:
        cur = db.cursor()

        cur.execute(
            """
            SELECT id
            FROM customers
            WHERE customer_ref = %s
            """,
            (data.customer_ref,)
        )

        if cur.fetchone():
            raise HTTPException(
                status_code=409,
                detail="Customer already exists"
            )

        cur.execute(
            """
            INSERT INTO customers (customer_ref, name)
            VALUES (%s, %s)
            RETURNING id, customer_ref, name, created_at
            """,
            (data.customer_ref, data.name)
        )

        row = cur.fetchone()
        db.commit()

        return {
            "id": row[0],
            "customer_ref": row[1],
            "name": row[2],
            "created_at": row[3]
        }

    finally:
        db.close()


@app.post("/api/payments")
def create_payment(
    data: PaymentCreate,
    x_api_key: str | None = Header(None)
):
    check_auth(x_api_key)

    db = get_db()

    try:
        cur = db.cursor()

        # Check customer
        cur.execute(
            "SELECT id FROM customers WHERE id = %s",
            (data.customer_id,)
        )

        if not cur.fetchone():
            raise HTTPException(
                status_code=404,
                detail="Customer not found"
            )

        # Idempotency check
        cur.execute(
            """
            SELECT id, transaction_ref, customer_id, amount,
                   status, created_at, completed_at, failure_code
            FROM transactions
            WHERE transaction_ref = %s
            """,
            (data.transaction_ref,)
        )

        existing = cur.fetchone()

        if existing:

            if (
                existing[2] != data.customer_id
                or Decimal(str(existing[3])) != data.amount
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Transaction reference already used"
                )

            return {
                "id": existing[0],
                "transaction_ref": existing[1],
                "customer_id": existing[2],
                "amount": float(existing[3]),
                "status": existing[4],
                "created_at": existing[5],
                "completed_at": existing[6],
                "failure_code": existing[7]
            }

        now = datetime.utcnow()

        cur.execute(
            """
            INSERT INTO transactions
            (
                transaction_ref,
                customer_id,
                amount,
                status,
                created_at,
                completed_at
            )
            VALUES (%s, %s, %s, 'SUCCESS', %s, %s)
            RETURNING
                id,
                transaction_ref,
                customer_id,
                amount,
                status,
                created_at,
                completed_at,
                failure_code
            """,
            (
                data.transaction_ref,
                data.customer_id,
                data.amount,
                now,
                now
            )
        )

        row = cur.fetchone()
        db.commit()

        return {
            "id": row[0],
            "transaction_ref": row[1],
            "customer_id": row[2],
            "amount": float(row[3]),
            "status": row[4],
            "created_at": row[5],
            "completed_at": row[6],
            "failure_code": row[7]
        }

    finally:
        db.close()


@app.get("/api/payments/{payment_id}")
def get_payment(
    payment_id: int,
    x_api_key: str | None = Header(None)
):
    check_auth(x_api_key)

    db = get_db()

    try:
        cur = db.cursor()

        cur.execute(
            """
            SELECT id, transaction_ref, customer_id, amount,
                   status, created_at, completed_at, failure_code
            FROM transactions
            WHERE id = %s
            """,
            (payment_id,)
        )

        row = cur.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Payment not found"
            )

        return {
            "id": row[0],
            "transaction_ref": row[1],
            "customer_id": row[2],
            "amount": float(row[3]),
            "status": row[4],
            "created_at": row[5],
            "completed_at": row[6],
            "failure_code": row[7]
        }

    finally:
        db.close()


@app.get("/api/customers/{customer_id}/payments")
def get_customer_payments(
    customer_id: int,
    x_api_key: str | None = Header(None)
):
    check_auth(x_api_key)

    db = get_db()

    try:
        cur = db.cursor()

        cur.execute(
            "SELECT id FROM customers WHERE id = %s",
            (customer_id,)
        )

        if not cur.fetchone():
            raise HTTPException(
                status_code=404,
                detail="Customer not found"
            )

        cur.execute(
            """
            SELECT id, transaction_ref, customer_id, amount,
                   status, created_at, completed_at, failure_code
            FROM transactions
            WHERE customer_id = %s
            ORDER BY created_at DESC
            """,
            (customer_id,)
        )

        rows = cur.fetchall()

        return [
            {
                "id": row[0],
                "transaction_ref": row[1],
                "customer_id": row[2],
                "amount": float(row[3]),
                "status": row[4],
                "created_at": row[5],
                "completed_at": row[6],
                "failure_code": row[7]
            }
            for row in rows
        ]

    finally:
        db.close()