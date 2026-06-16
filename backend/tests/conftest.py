import pytest
from backend.app import create_app
from backend.database.connection import init_test_pool, execute_schema, get_conn, release_conn
from backend.services import patient_service as svc

@pytest.fixture(scope="session")
def app():
    """Create Flask test app using test DB."""
    application = create_app(testing=True)
    yield application

@pytest.fixture(scope="session")
def setup_test_db(app):
    """Create schema in test DB once per session."""
    execute_schema()
    yield
    # Teardown: drop all tables in test DB after session
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS audit_log, patients CASCADE")
        conn.commit()
    finally:
        release_conn(conn)

@pytest.fixture(autouse=True)
def clean_db(setup_test_db):
    """Truncate tables and reset heap before every test."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE audit_log, patients RESTART IDENTITY CASCADE")
        conn.commit()
    finally:
        release_conn(conn)
    svc._queue.__init__()   # reset in-memory heap

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def make_patient_dict():
    def _make(name="Test Patient", age=35, gender="Male",
              condition="chest pain", priority=4,
              ai_suggested=4, ai_reasoning="Test reason"):
        return {
            "name"                 : name,
            "age"                  : age,
            "gender"               : gender,
            "condition"            : condition,
            "priority"             : priority,
            "ai_suggested_priority": ai_suggested,
            "ai_reasoning"         : ai_reasoning
        }
    return _make
