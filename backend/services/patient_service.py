import os
import uuid
from datetime import datetime, timezone

from psycopg2.extras import RealDictCursor

from backend.database.connection import get_conn, release_conn
from backend.models.patient import Patient, PRIORITY_LABELS
from backend.models.priority_queue import HospitalPriorityQueue

_queue = HospitalPriorityQueue()
AGING_INTERVAL_MINUTES = int(os.getenv("QUEUE_AGING_INTERVAL_MINUTES", 120))
AGING_ALERT_MINUTES = int(os.getenv("QUEUE_AGING_ALERT_MINUTES", 180))


def _to_datetime(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise TypeError("Unsupported datetime value")


def _wait_minutes_since(arrival_time) -> int:
    arrival = _to_datetime(arrival_time)
    now = datetime.now(timezone.utc)
    return max(0, int((now - arrival).total_seconds() // 60))


def _apply_waiting_aging() -> int:
    """
    Escalate waiting patients based on time spent in queue.
    Every AGING_INTERVAL_MINUTES adds one priority level, capped at 5.
    """
    conn = get_conn()
    updated = 0
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, priority, arrival_time
                FROM patients
                WHERE status = 'waiting'
                ORDER BY arrival_time ASC
                """
            )
            for row in cur.fetchall():
                wait_minutes = _wait_minutes_since(row["arrival_time"])
                increments = wait_minutes // AGING_INTERVAL_MINUTES
                if increments <= 0:
                    continue

                current_priority = int(row["priority"])
                new_priority = min(5, current_priority + increments)
                if new_priority <= current_priority:
                    continue

                cur.execute(
                    """
                    UPDATE patients
                    SET priority = %s, priority_label = %s
                    WHERE id = %s AND status = 'waiting'
                    """,
                    (new_priority, PRIORITY_LABELS[new_priority], row["id"]),
                )
                _write_audit(
                    cur,
                    row["id"],
                    "auto_age_priority",
                    current_priority,
                    new_priority,
                    f"Auto-escalated after {wait_minutes} minutes waiting",
                )
                updated += 1
        conn.commit()
        return updated
    finally:
        release_conn(conn)


def rebuild_heap() -> None:
    """
    Load all waiting patients from PostgreSQL and insert into the in-memory heap.
    Also applies wait-time aging before rebuilding so stale queues are refreshed.
    """
    global _queue
    _apply_waiting_aging()
    _queue = HospitalPriorityQueue()
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM patients
                WHERE status = 'waiting'
                ORDER BY priority DESC, arrival_time ASC
                """
            )
            for row in cur.fetchall():
                _queue.insert(Patient.from_row(row))
    finally:
        release_conn(conn)


def register_patient(
    name: str,
    age: int,
    gender: str,
    condition: str,
    priority: int,
    ai_suggested_priority: int = 0,
    ai_reasoning: str = "",
) -> Patient:
    """
    Validate, write to PostgreSQL, insert into heap, write audit log.
    Returns the created Patient. Raises ValueError on validation failure.
    """
    rebuild_heap()

    if not name or not name.strip():
        raise ValueError("Name is required")
    if not 1 <= age <= 120:
        raise ValueError("Age must be 1-120")
    if gender not in ("Male", "Female", "Other"):
        raise ValueError("Invalid gender")
    if not condition or not condition.strip():
        raise ValueError("Condition is required")
    if not 1 <= priority <= 5:
        raise ValueError("Priority must be 1-5")

    patient = Patient(
        id=str(uuid.uuid4()),
        name=name.strip(),
        age=age,
        gender=gender,
        condition=condition.strip(),
        priority=priority,
        priority_label=PRIORITY_LABELS[priority],
        ai_suggested_priority=ai_suggested_priority,
        ai_reasoning=ai_reasoning,
        arrival_time=datetime.now(timezone.utc).isoformat(),
        status="waiting",
    )

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO patients
                  (id, name, age, gender, condition, priority, priority_label,
                   ai_suggested_priority, ai_reasoning, arrival_time, status)
                VALUES
                  (%(id)s, %(name)s, %(age)s, %(gender)s, %(condition)s,
                   %(priority)s, %(priority_label)s, %(ai_suggested_priority)s,
                   %(ai_reasoning)s, %(arrival_time)s, %(status)s)
                """,
                patient.to_dict(),
            )
            _write_audit(cur, patient.id, "register", None, priority, "Patient registered")
        conn.commit()
    finally:
        release_conn(conn)

    _queue.insert(patient)
    return patient


def get_waiting_queue() -> list:
    """Return all waiting patients sorted by priority desc as list of dicts."""
    rebuild_heap()
    return [p.to_dict() for p in _queue.to_sorted_list()]


def admit_next_patient() -> Patient:
    """
    ExtractMax from heap, update status='admitted' + admitted_at in DB,
    write audit log. Raises IndexError if queue is empty.
    """
    rebuild_heap()
    if _queue.is_empty():
        raise IndexError("Queue is empty")

    patient = _queue.extract_max()
    patient.status = "admitted"
    patient.admitted_at = datetime.now(timezone.utc).isoformat()

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE patients
                SET status = 'admitted', admitted_at = %(admitted_at)s
                WHERE id = %(id)s
                """,
                {"id": patient.id, "admitted_at": patient.admitted_at},
            )
            _write_audit(cur, patient.id, "admit", patient.priority, None, "Patient admitted")
        conn.commit()
    finally:
        release_conn(conn)

    return patient


def update_priority(patient_id: str, new_priority: int) -> bool:
    """
    Update priority in heap and DB. Write audit log with old/new priority.
    Returns True if patient found, False otherwise.
    Raises ValueError if new_priority not 1-5.
    """
    rebuild_heap()
    if not 1 <= new_priority <= 5:
        raise ValueError("Priority must be 1-5")

    old_priority = None
    for patient in _queue.to_sorted_list():
        if patient.id == patient_id:
            old_priority = patient.priority
            break
    if old_priority is None:
        return False

    found = _queue.update_priority(patient_id, new_priority)
    if not found:
        return False

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE patients
                SET priority = %(priority)s,
                    priority_label = %(label)s
                WHERE id = %(id)s AND status = 'waiting'
                """,
                {
                    "priority": new_priority,
                    "label": PRIORITY_LABELS[new_priority],
                    "id": patient_id,
                },
            )
            _write_audit(
                cur,
                patient_id,
                "update_priority",
                old_priority,
                new_priority,
                "Priority updated",
            )
        conn.commit()
    finally:
        release_conn(conn)

    return True


def remove_patient(patient_id: str) -> bool:
    """
    Remove patient from heap and mark status='removed' in DB.
    Returns True if found, False otherwise.
    """
    rebuild_heap()
    found = _queue.remove(patient_id)
    if not found:
        return False

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE patients SET status = 'removed' WHERE id = %s", (patient_id,))
            _write_audit(cur, patient_id, "remove", None, None, "Patient removed")
        conn.commit()
    finally:
        release_conn(conn)

    return True


def get_stats() -> dict:
    """
    Compute live stats from DB (not heap) for accuracy.
    Returns: total, by_priority counts, avg_wait_minutes, treated_today.
    """
    rebuild_heap()
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN priority=5 THEN 1 ELSE 0 END) AS p5,
                    SUM(CASE WHEN priority=4 THEN 1 ELSE 0 END) AS p4,
                    SUM(CASE WHEN priority=3 THEN 1 ELSE 0 END) AS p3,
                    SUM(CASE WHEN priority=2 THEN 1 ELSE 0 END) AS p2,
                    SUM(CASE WHEN priority=1 THEN 1 ELSE 0 END) AS p1,
                    AVG(EXTRACT(EPOCH FROM (NOW() - arrival_time)) / 60) AS avg_wait
                FROM patients
                WHERE status = 'waiting'
                """
            )
            row = cur.fetchone()
            cur.execute(
                """
                SELECT COUNT(*) AS treated
                FROM patients
                WHERE status = 'admitted'
                AND admitted_at::date = CURRENT_DATE
                """
            )
            treated = cur.fetchone()

        return {
            "total": int(row["total"] or 0),
            "by_priority": {
                "5": int(row["p5"] or 0),
                "4": int(row["p4"] or 0),
                "3": int(row["p3"] or 0),
                "2": int(row["p2"] or 0),
                "1": int(row["p1"] or 0),
            },
            "average_wait_minutes": round(float(row["avg_wait"] or 0), 1),
            "treated_today": int(treated["treated"] or 0),
            "queue_size": _queue.size(),
        }
    finally:
        release_conn(conn)


def get_history() -> list:
    """Return all admitted patients from DB ordered by admitted_at desc."""
    rebuild_heap()
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM patients
                WHERE status = 'admitted'
                ORDER BY admitted_at DESC
                """
            )
            return [Patient.from_row(row).to_dict() for row in cur.fetchall()]
    finally:
        release_conn(conn)


def get_all_patients_db() -> list:
    """Return ALL patients from DB (all statuses) for audit/admin use."""
    rebuild_heap()
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM patients ORDER BY arrival_time DESC")
            return [Patient.from_row(row).to_dict() for row in cur.fetchall()]
    finally:
        release_conn(conn)


def _write_audit(cur, patient_id, action, old_priority, new_priority, notes):
    """Insert one row into audit_log using an existing cursor (no commit here)."""
    cur.execute(
        """
        INSERT INTO audit_log (patient_id, action, old_priority, new_priority, notes)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (patient_id, action, old_priority, new_priority, notes),
    )
