from pathlib import Path
import re
import sqlite3

from psycopg2 import OperationalError, pool as pg_pool

from backend.config import Config

_pool: pg_pool.ThreadedConnectionPool = None
_sqlite_mode = False


class _SQLiteCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self._cursor.close()

    def execute(self, sql, params=None):
        sql = self._translate_sql(sql)
        if isinstance(params, dict):
            params = {key: self._serialize(value) for key, value in params.items()}
        elif params is not None:
            params = tuple(self._serialize(value) for value in params)
        self._cursor.execute(sql, params or ())
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        return dict(row) if row is not None else None

    def fetchall(self):
        return [dict(row) for row in self._cursor.fetchall()]

    @staticmethod
    def _serialize(value):
        return str(value) if hasattr(value, "hex") and hasattr(value, "version") else value

    @staticmethod
    def _translate_sql(sql):
        sql = re.sub(r"%\(([^)]+)\)s", r":\1", sql)
        return sql.replace("%s", "?")


class _SQLiteConnection:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self, *args, **kwargs):
        return _SQLiteCursor(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()


class _SQLitePool:
    def __init__(self, db_path):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def getconn(self):
        return _SQLiteConnection(self._conn)

    def putconn(self, conn):
        pass


def using_sqlite():
    return _sqlite_mode


def _init_sqlite_pool(test=False):
    global _pool, _sqlite_mode
    project_root = Path(__file__).resolve().parents[2]
    db_name = "hospital_queue_test.sqlite3" if test else "hospital_queue.sqlite3"
    _pool = _SQLitePool(project_root / db_name)
    _sqlite_mode = True

def init_pool():
    """Initialize connection pool. Call once at app startup."""
    global _pool, _sqlite_mode
    try:
        _pool = pg_pool.ThreadedConnectionPool(
            minconn=2, maxconn=10,
            **Config.get_dsn()
        )
        _sqlite_mode = False
    except OperationalError:
        print("PostgreSQL is unavailable; using local SQLite database for development.")
        _init_sqlite_pool()

def init_test_pool():
    """Initialize pool pointing to test database."""
    global _pool, _sqlite_mode
    try:
        _pool = pg_pool.ThreadedConnectionPool(
            minconn=1, maxconn=5,
            **Config.get_dsn(test=True)
        )
        _sqlite_mode = False
    except OperationalError:
        _init_sqlite_pool(test=True)

def get_conn():
    """Get a connection from the pool. Always use with release_conn()."""
    return _pool.getconn()

def release_conn(conn):
    """Return connection to pool."""
    _pool.putconn(conn)

def execute_schema():
    """Run schema.sql against the current pool's database."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if using_sqlite():
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS patients (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL CHECK (length(trim(name)) > 0),
                        age INTEGER NOT NULL CHECK (age >= 1 AND age <= 120),
                        gender TEXT NOT NULL CHECK (gender IN ('Male','Female','Other')),
                        condition TEXT NOT NULL CHECK (length(trim(condition)) > 0),
                        priority INTEGER NOT NULL CHECK (priority >= 1 AND priority <= 5),
                        priority_label TEXT NOT NULL,
                        ai_suggested_priority INTEGER NOT NULL DEFAULT 0,
                        ai_reasoning TEXT NOT NULL DEFAULT '',
                        arrival_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        status TEXT NOT NULL DEFAULT 'waiting'
                               CHECK (status IN ('waiting','admitted','removed')),
                        admitted_at TEXT
                    )
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_patients_status ON patients(status)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_patients_priority ON patients(priority DESC)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_patients_arrival ON patients(arrival_time)")
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        patient_id TEXT REFERENCES patients(id) ON DELETE SET NULL,
                        action TEXT NOT NULL,
                        old_priority INTEGER,
                        new_priority INTEGER,
                        performed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        notes TEXT
                    )
                    """
                )
            else:
                schema_path = Path(__file__).with_name("schema.sql")
                cur.execute(schema_path.read_text())
        conn.commit()
    finally:
        release_conn(conn)
