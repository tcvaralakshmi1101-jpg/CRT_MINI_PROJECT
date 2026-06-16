from psycopg2 import pool as pg_pool
from backend.config import Config
import psycopg2.extras

_pool: pg_pool.ThreadedConnectionPool = None

def init_pool():
    """Initialize connection pool. Call once at app startup."""
    global _pool
    _pool = pg_pool.ThreadedConnectionPool(
        minconn=2, maxconn=10,
        **Config.get_dsn()
    )

def init_test_pool():
    """Initialize pool pointing to test database."""
    global _pool
    _pool = pg_pool.ThreadedConnectionPool(
        minconn=1, maxconn=5,
        **Config.get_dsn(test=True)
    )

def get_conn():
    """Get a connection from the pool. Always use with release_conn()."""
    return _pool.getconn()

def release_conn(conn):
    """Return connection to pool."""
    _pool.putconn(conn)

def execute_schema():
    """Run schema.sql against the current pool's database."""
    import os
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r") as f:
        sql = f.read()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        release_conn(conn)
