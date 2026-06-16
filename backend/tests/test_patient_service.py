import pytest
from backend.services import patient_service as svc
from backend.database.connection import get_conn, release_conn
from psycopg2.extras import RealDictCursor

def test_register_patient_persists_to_db(clean_db):
    """Test that register_patient() writes to database."""
    patient = svc.register_patient("John Doe", 35, "Male", "chest pain", 4)
    
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM patients WHERE id = %s", (patient.id,))
            row = cur.fetchone()
        assert row is not None
        assert row["name"] == "John Doe"
        assert row["priority"] == 4
    finally:
        release_conn(conn)

def test_register_patient_adds_to_heap(clean_db):
    """Test that register_patient() inserts into in-memory heap."""
    size_before = svc._queue.size()
    svc.register_patient("Jane Doe", 40, "Female", "fever", 3)
    size_after = svc._queue.size()
    assert size_after == size_before + 1

def test_register_empty_name_raises_value_error(clean_db):
    """Test that registering with empty name raises ValueError."""
    with pytest.raises(ValueError):
        svc.register_patient("", 35, "Male", "test", 3)

def test_register_invalid_age_raises_value_error(clean_db):
    """Test that registering with invalid age raises ValueError."""
    with pytest.raises(ValueError):
        svc.register_patient("Test", 200, "Male", "test", 3)

def test_register_invalid_priority_raises_value_error(clean_db):
    """Test that registering with invalid priority raises ValueError."""
    with pytest.raises(ValueError):
        svc.register_patient("Test", 35, "Male", "test", 6)

def test_get_waiting_queue_returns_sorted_list(clean_db):
    """Test that get_waiting_queue() returns patients sorted by priority desc."""
    svc.register_patient("Low", 30, "Male", "mild", 2)
    svc.register_patient("High", 40, "Female", "severe", 5)
    svc.register_patient("Mid", 50, "Male", "moderate", 3)
    
    queue = svc.get_waiting_queue()
    assert len(queue) == 3
    assert queue[0]["priority"] == 5
    assert queue[1]["priority"] == 3
    assert queue[2]["priority"] == 2

def test_admit_next_returns_highest_priority_patient(clean_db):
    """Test that admit_next_patient() returns highest priority."""
    svc.register_patient("Low", 30, "Male", "mild", 2)
    svc.register_patient("High", 40, "Female", "severe", 5)
    
    admitted = svc.admit_next_patient()
    assert admitted.priority == 5

def test_admit_next_updates_db_status_to_admitted(clean_db):
    """Test that admit_next_patient() sets status='admitted' in DB."""
    patient = svc.register_patient("Test", 35, "Male", "chest pain", 4)
    svc.admit_next_patient()
    
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT status FROM patients WHERE id = %s", (patient.id,))
            row = cur.fetchone()
        assert row["status"] == "admitted"
    finally:
        release_conn(conn)

def test_admit_next_sets_admitted_at_timestamp(clean_db):
    """Test that admit_next_patient() sets admitted_at."""
    svc.register_patient("Test", 35, "Male", "chest pain", 4)
    admitted = svc.admit_next_patient()
    assert admitted.admitted_at is not None

def test_admit_next_empty_queue_raises_index_error(clean_db):
    """Test that admit_next_patient() raises IndexError on empty queue."""
    with pytest.raises(IndexError):
        svc.admit_next_patient()

def test_update_priority_reflects_in_db(clean_db):
    """Test that update_priority() updates DB."""
    patient = svc.register_patient("Test", 35, "Male", "chest pain", 2)
    svc.update_priority(patient.id, 5)
    
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT priority FROM patients WHERE id = %s", (patient.id,))
            row = cur.fetchone()
        assert row["priority"] == 5
    finally:
        release_conn(conn)

def test_remove_patient_sets_db_status_removed(clean_db):
    """Test that remove_patient() sets status='removed' in DB."""
    patient = svc.register_patient("Test", 35, "Male", "chest pain", 4)
    svc.remove_patient(patient.id)
    
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT status FROM patients WHERE id = %s", (patient.id,))
            row = cur.fetchone()
        assert row["status"] == "removed"
    finally:
        release_conn(conn)
