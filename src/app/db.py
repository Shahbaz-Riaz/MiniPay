import os
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgrespassword@db:5432/minipay")

# Create connection pool
db_pool = pool.SimpleConnectionPool(1, 20, DATABASE_URL)

def get_db():
    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        db_pool.putconn(conn)