import json, os
from backend.database.connection import get_conn, release_conn

def seed_sample_data():
    """Insert sample patients from sample_data/sample_patients.json.
    Safe to run multiple times — skips duplicates via ON CONFLICT DO NOTHING."""
    root = os.path.join(os.path.dirname(__file__), "..", "..", "sample_data")
    path = os.path.join(root, "sample_patients.json")
    with open(path) as f:
        patients = json.load(f)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for p in patients:
                cur.execute("""
                    INSERT INTO patients
                      (id, name, age, gender, condition, priority, priority_label,
                       ai_suggested_priority, ai_reasoning, arrival_time, status)
                    VALUES
                      (%(id)s, %(name)s, %(age)s, %(gender)s, %(condition)s,
                       %(priority)s, %(priority_label)s, %(ai_suggested_priority)s,
                       %(ai_reasoning)s, %(arrival_time)s, %(status)s)
                    ON CONFLICT (id) DO NOTHING
                """, p)
        conn.commit()
        print(f"[Seed] Inserted up to {len(patients)} sample patients.")
    finally:
        release_conn(conn)
