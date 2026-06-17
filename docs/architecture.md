# 🏗️ Architecture Deep Dive — Hospital Emergency Queue Management

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Browser (SPA)                                │
│                    HTML5 + CSS3 + Vanilla JS                         │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ Register │  │  Search  │  │  Admit   │  │ History  │            │
│  │  Panel   │  │ & Filter │  │ Controls │  │  View    │            │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘            │
│        │              │              │              │                │
│        └──────────────┴──────────────┴──────────────┘                │
│                       │                                              │
│              fetch() + JSON responses                                │
└───────────────────────┬──────────────────────────────────────────────┘
                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│              Flask REST API (:5000)                                  │
│                                                                      │
│  app.py (Flask Factory)                                             │
│  ├─ create_app(testing=False)                                       │
│  ├─ register blueprints                                             │
│  ├─ global error handlers                                           │
│  └─ serve frontend /                                                │
│                                                                      │
│  Blueprints:                                                         │
│  ├─ patient_routes.py (9 endpoints)                                 │
│  │   ├─ POST   /api/patients (register)                            │
│  │   ├─ GET    /api/patients (get queue)                           │
│  │   ├─ POST   /api/patients/admit-next                            │
│  │   ├─ PUT    /api/patients/<id>/priority                         │
│  │   ├─ DELETE /api/patients/<id>                                  │
│  │   ├─ GET    /api/history                                        │
│  │   ├─ GET    /api/stats                                          │
│  │   ├─ GET    /api/patients/all                                   │
│  │   └─ POST   /api/suggest-priority                               │
│  │                                                                   │
│  └─ health_routes.py (2 endpoints)                                  │
│      └─ GET    /api/health                                         │
│                                                                      │
│  Error Handlers:                                                     │
│  ├─ 404: Endpoint not found                                         │
│  ├─ 405: Method not allowed                                         │
│  └─ 500: Internal server error                                      │
│                                                                      │
└───────────────────┬──────────────────────────────────────────────────┘
                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│          Service Layer (Business Logic)                              │
│                                                                      │
│  patient_service.py:                                                │
│  ├─ rebuild_heap()          [on app startup]                        │
│  ├─ register_patient()       [validate, write DB, update heap]      │
│  ├─ get_waiting_queue()      [return heap as sorted list]           │
│  ├─ admit_next_patient()     [extract_max, update DB, audit]        │
│  ├─ update_priority()        [update heap + DB, audit]              │
│  ├─ remove_patient()         [remove from heap + DB, audit]         │
│  ├─ get_stats()              [compute live stats from DB]           │
│  ├─ get_history()            [return admitted patients]             │
│  └─ get_all_patients_db()    [admin: all patients, all statuses]    │
│                                                                      │
│  gemini_service.py:                                                 │
│  ├─ suggest_priority()       [call Gemini API, parse JSON]          │
│  └─ health_check()           [verify Gemini connectivity]           │
│                                                                      │
│  Key Property: Every mutation follows dual-write pattern            │
│  ├─ 1. Validate input (age, priority, gender, etc)                 │
│  ├─ 2. Write to PostgreSQL FIRST (source of truth)                 │
│  ├─ 3. Update in-memory MaxHeap (speed layer)                       │
│  ├─ 4. Write to audit_log (every action tracked)                    │
│  └─ 5. Return success/error to frontend                             │
│                                                                      │
└──────┬──────────────────────────────┬────────────────────┬──────────┘
       │                              │                    │
       ▼                              ▼                    ▼
┌──────────────────┐    ┌──────────────────┐   ┌─────────────────┐
│  Priority Queue  │    │   Data Models    │   │  External API   │
│  (In-Memory)     │    │                  │   │                 │
│                  │    │ patient.py:      │   │ Gemini 2.5      │
│  MaxHeap {       │    │  ├─ Patient      │   │ Flash API       │
│    _heap: []     │    │  │  (dataclass)  │   │                 │
│    O(log n)      │    │  └─ PRIORITY_    │   │ Input:          │
│    operations    │    │     LABELS       │   │ name, age,      │
│  }               │    │                  │   │ condition       │
│                  │    │ priority_queue.py│   │                 │
│  Rebuilt from DB │    │  ├─ HospitalPQ  │   │ Output:         │
│  on app startup  │    │  │ (Max-Heap)   │   │ {priority,      │
│                  │    │  ├─ insert()    │   │  label,         │
│  Methods:        │    │  ├─ extract_max │   │  reasoning}     │
│  ├─ insert()     │    │  ├─ peek()      │   │                 │
│  ├─ extract_max()│    │  ├─ update_prio │   │ Fallback:       │
│  ├─ peek()       │    │  ├─ remove()    │   │ Priority 3      │
│  ├─ update_()    │    │  └─ to_sorted_  │   │ (Moderate)      │
│  ├─ remove()     │    │     list()      │   │ on API error     │
│  └─ size()       │    │                  │   │                 │
│                  │    └──────────────────┘   └─────────────────┘
└──────────────────┘
       │
       │ (via psycopg2 connection pool)
       │
       ▼
┌──────────────────────────────────────────────────────────────────────┐
│          Database Layer (PostgreSQL 14+)                             │
│                                                                      │
│  Connection Pooling:                                                 │
│  ├─ ThreadedConnectionPool(minconn=2, maxconn=10)                  │
│  ├─ get_conn() — borrow from pool                                   │
│  ├─ release_conn() — return to pool                                 │
│  └─ Always use try/finally to prevent pool exhaustion              │
│                                                                      │
│  Tables:                                                             │
│                                                                      │
│  patients (main table):                                             │
│  ├─ id (UUID PK) — unique identifier                               │
│  ├─ name, age, gender, condition — patient demographics            │
│  ├─ priority (1-5) — final doctor-assigned priority                │
│  ├─ priority_label — derived from priority                         │
│  ├─ ai_suggested_priority — Gemini's suggestion                    │
│  ├─ ai_reasoning — one-sentence Gemini explanation                 │
│  ├─ arrival_time (TIMESTAMPTZ) — when registered                   │
│  ├─ status — 'waiting' | 'admitted' | 'removed'                   │
│  ├─ admitted_at (TIMESTAMPTZ) — when admitted                      │
│  │                                                                   │
│  │  Indexes:                                                        │
│  │  ├─ idx_patients_status (WHERE status = 'waiting')              │
│  │  ├─ idx_patients_priority DESC (ORDER BY priority)              │
│  │  └─ idx_patients_arrival (ORDER BY arrival_time)                │
│  │                                                                   │
│  │  Constraints:                                                    │
│  │  ├─ name NOT NULL, length > 0                                   │
│  │  ├─ age 1-120 range                                             │
│  │  ├─ gender IN ('Male','Female','Other')                         │
│  │  ├─ priority 1-5 range                                          │
│  │  └─ status IN ('waiting','admitted','removed')                  │
│  │                                                                   │
│  └─ Rows inserted by: register_patient()                            │
│     Rows updated by: admit_next_patient(), update_priority(),       │
│                      remove_patient()                               │
│                                                                      │
│  audit_log (immutable audit trail):                                │
│  ├─ id (SERIAL PK)                                                 │
│  ├─ patient_id (FK → patients.id)                                  │
│  ├─ action — 'register' | 'admit' | 'update_priority' | 'remove'   │
│  ├─ old_priority — before change (NULL if N/A)                    │
│  ├─ new_priority — after change (NULL if N/A)                     │
│  ├─ performed_at (TIMESTAMPTZ) — when action occurred              │
│  └─ notes — additional context                                     │
│                                                                      │
│     Rows inserted by: Every mutation in PatientService             │
│     Example entries:                                                │
│     ├─ patient_id=uuid-1, action='register', new_priority=5        │
│     ├─ patient_id=uuid-1, action='admit', old_priority=5           │
│     ├─ patient_id=uuid-2, action='update_priority', old=2, new=5   │
│     └─ patient_id=uuid-3, action='remove', old_priority=3          │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Data Persistence Model (Dual-Write Strategy)

### Why Dual-Layer?

**Problem:** Sorting a list of 1000 waiting patients on every query is O(n log n) = slow.

**Solution:** Keep a Max-Heap in memory for O(log n) admit operations.

**Risk:** Server crash → lose in-memory heap.

**Solution:** DB is source of truth. Rebuild heap on startup.

### Flow: Patient Registration Example

```
┌─── 1. Frontend: Doctor fills form ───┐
│ Name: "Rajesh Venkataraman"           │
│ Age: 58                               │
│ Condition: "Unresponsive, no pulse"   │
│ Priority: 5 (Critical)                │
└───────────────────────────────────────┘
         │
         │ POST /api/patients
         ▼
┌─── 2. Flask Route ───┐
│ extract JSON payload │
│ pass to service      │
└─────────────────────┘
         │
         ▼
┌─── 3. PatientService.register_patient() ───┐
│                                              │
│ ├─ Validate input                           │
│ │  └─ age 1-120? ✓                          │
│ │  └─ gender in enum? ✓                     │
│ │  └─ priority 1-5? ✓                       │
│ │                                            │
│ ├─ Create Patient dataclass                 │
│ │  └─ id = uuid.uuid4()                     │
│ │  └─ arrival_time = now()                  │
│ │  └─ status = "waiting"                    │
│ │                                            │
│ ├─ WRITE TO DATABASE (source of truth)      │
│ │  └─ INSERT INTO patients (...)            │
│ │     on CONFLICT DO NOTHING                │
│ │                                            │
│ ├─ UPDATE IN-MEMORY HEAP                    │
│ │  └─ _queue.insert(patient)                │
│ │     └─ O(log n) time                      │
│ │                                            │
│ ├─ AUDIT LOG WRITE                          │
│ │  └─ INSERT INTO audit_log                 │
│ │     (patient_id, action='register',       │
│ │      new_priority=5, ...)                 │
│ │                                            │
│ ├─ COMMIT transaction                       │
│ │                                            │
│ └─ Return Patient object to Flask           │
│                                              │
└──────────────────────────────────────────────┘
         │
         ▼
┌─── 4. Flask Response ───┐
│ status: 201 Created      │
│ body: {                  │
│   success: true,         │
│   patient: {             │
│     id: "uuid-...",      │
│     name: "Rajesh...",   │
│     priority: 5,         │
│     ...                  │
│   }                      │
│ }                        │
└──────────────────────────┘
         │
         ▼
┌─── 5. Frontend ───┐
│ ├─ Show toast     │
│ ├─ Re-render queue│
│ ├─ Update stats   │
│ └─ Reset form     │
└────────────────────┘
```

### Disaster Recovery Example (Server Crash)

```
TIME: 08:00 AM — Server running normally
├─ Heap has 50 patients (in memory)
└─ Database has 50 patients (persistent)

TIME: 08:15 AM — Server CRASHES
├─ Heap evaporates (RAM lost)
└─ Database still has 50 patients ✓

TIME: 08:16 AM — Server restarts
├─ app.py: create_app() called
├─ execute_schema() — creates tables
├─ rebuild_heap():
│  └─ SELECT * FROM patients WHERE status = 'waiting'
│  └─ Insert all 50 rows back into heap
│  └─ Heap rebuilt in ~100ms ✓
└─ System fully operational again ✓

RESULT: ZERO DATA LOSS
```

---

## Queue Aging and Starvation Protection

The service layer now includes a fairness mechanism so very long-waiting patients are not stuck behind newer arrivals forever.

Behavior:
- `Patient.to_dict()` exposes `wait_minutes` and `needs_attention`
- `rebuild_heap()` applies waiting-time aging before reloading the in-memory heap from PostgreSQL
- `register_patient()`, `get_waiting_queue()`, `admit_next_patient()`, `update_priority()`, `remove_patient()`, `get_stats()`, and `get_history()` rebuild the heap before returning data
- Every `QUEUE_AGING_INTERVAL_MINUTES` minutes of waiting, a patient is escalated by 1 priority level, up to priority 5
- After `QUEUE_AGING_ALERT_MINUTES`, the frontend can mark the patient as needing attention

Default environment values:
- `QUEUE_AGING_INTERVAL_MINUTES=120`
- `QUEUE_AGING_ALERT_MINUTES=180`

Operational result:
- Critical patients still stay at the top
- Long-waiting lower-priority patients gradually move upward
- Doctors still control the final priority and can override suggestions anytime

Sample data support:
- `backend/seed_sample_data.py` resets the schema and loads `sample_data/sample_patients.json`
- `sample_data/expected_queue_order.json` documents the expected waiting order after seeding

---

## Max-Heap Internals

### Visual Structure

```
         Rajesh (P5)
        /            \
    Arjun (P4)    Venkat (P3)
    /      \
Suresh   Anitha
(P2)     (P2)

Key Property: Parent.priority ≥ children.priority (ALWAYS)
Example: 5 ≥ 4 ✓, 5 ≥ 3 ✓, 4 ≥ 2 ✓, 4 ≥ 2 ✓
```

### Array Representation (what actually happens in memory)

```
Index:    0          1         2         3      4      5
Data:   [Rajesh(5), Arjun(4), Venkat(3), P2,   P2,   ...]
                     /    \
                Parent of: Index 0
                → Left child = 2*0+1 = 1 (Arjun)
                → Right child = 2*0+2 = 2 (Venkat)
```

### Insert Operation: O(log n)

```
Step 1: Append to end
Queue: [5, 4, 3, 2, 2, NEW_2]

Step 2: Bubble up
  NEW_2 parent = (5-1)//2 = 2 (Venkat, P3)
  NEW_2 (P2) > Venkat (P3)? NO → STOP
  Result: [5, 4, 3, 2, 2, 2]

Time: O(log n) — max height = log(n)
```

### Extract Max: O(log n)

```
Step 1: Save root (max element)
  max_patient = Rajesh (P5)

Step 2: Move last element to root
  Root = last element = P2 (someone with priority 2)
  Heap: [P2, 4, 3, 2, 2]

Step 3: Heapify down
  P2 has children: Arjun (P4), Venkat (P3)
  Largest child = Arjun (P4)
  P2 < Arjun? YES → SWAP
  Heap: [4, P2, 3, 2, 2]

Step 4: Continue heapify
  P2 children = [P2, (none)]
  No valid children with higher priority → STOP

Result: 
  Returned: Rajesh (P5) ✓
  Heap: [4, P2, 3, 2, 2]

Time: O(log n) — max height = log(n)
```

### Update Priority: O(n) search + O(log n) heapify

```
Query: "Update patient Venkat from P3 to P5"

Step 1: Find Venkat
  Scan heap for id match
  Found at index 2, current priority = 3
  Time: O(n) ← weakness, but acceptable for <1000 patients

Step 2: Update priority
  heap[2].priority = 5

Step 3: Bubble up (priority increased)
  Venkat (now P5) parent = Rajesh (P5)
  5 > 5? NO → STOP

Step 4: OR heapify down (priority decreased)
  Would be needed if priority decreased

Result: Heap maintains max-heap property
  [Rajesh(P5), Arjun(P4), Venkat(P5), ...]
  (two P5s both valid at top)

Time: O(n) search + O(log n) heapify = O(n)
```

---

## API Endpoint Deep Dive

### POST /api/suggest-priority

```
REQUEST:
POST /api/suggest-priority
Content-Type: application/json

{
  "name": "Rajesh Venkataraman",
  "age": 58,
  "condition": "Unresponsive, no pulse detected, CPR in progress"
}

RESPONSE (200 OK):
{
  "priority": 5,
  "label": "Critical",
  "reasoning": "Cardiac arrest—immediate intervention required; initiate ACLS protocol."
}

RESPONSE (400 Bad Request):
{
  "error": "Age must be an integer between 1 and 120"
}

Flow:
  1. Validate name, age, condition present
  2. Call gemini_service.suggest_priority(name, age, condition)
  3. Gemini API call with clinical prompt
  4. Parse JSON response
  5. Return to frontend
  6. Frontend displays in purple box for doctor review
```

### POST /api/patients

```
REQUEST:
POST /api/patients
{
  "name": "Rajesh Venkataraman",
  "age": 58,
  "gender": "Male",
  "condition": "Unresponsive, no pulse detected, CPR in progress",
  "priority": 5,
  "ai_suggested_priority": 5,
  "ai_reasoning": "Cardiac arrest—immediate intervention required."
}

RESPONSE (201 Created):
{
  "success": true,
  "patient": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Rajesh Venkataraman",
    "age": 58,
    "gender": "Male",
    "condition": "Unresponsive, no pulse detected, CPR in progress",
    "priority": 5,
    "priority_label": "Critical",
    "ai_suggested_priority": 5,
    "ai_reasoning": "Cardiac arrest—immediate intervention required.",
    "arrival_time": "2026-06-16T08:00:00Z",
    "status": "waiting",
    "admitted_at": null
  }
}

RESPONSE (400 Bad Request):
{
  "error": "Age must be 1–120"
}

Database effect:
  INSERT INTO patients (id, name, age, ..., status)
  VALUES (uuid-123, 'Rajesh', 58, ..., 'waiting')
  
Heap effect:
  _queue.insert(patient)  ← O(log n)
  
Audit effect:
  INSERT INTO audit_log (patient_id, action, new_priority, notes)
  VALUES (uuid-123, 'register', 5, 'Patient registered')
```

### POST /api/patients/admit-next

```
REQUEST:
POST /api/patients/admit-next

RESPONSE (200 OK):
{
  "admitted": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Rajesh Venkataraman",
    "priority": 5,
    "status": "admitted",
    "admitted_at": "2026-06-16T08:05:32Z"
  },
  "remaining_in_queue": 49
}

RESPONSE (404 Not Found):
{
  "error": "Queue is empty"
}

Algorithm:
  1. IF queue.is_empty(): return 404
  2. patient = queue.extract_max()  ← O(log n)
  3. patient.status = 'admitted'
  4. patient.admitted_at = now()
  5. UPDATE patients SET status='admitted', admitted_at=... WHERE id=...
  6. INSERT INTO audit_log (..., action='admit', ...)
  7. COMMIT
  8. Return patient + remaining_count
```

---

## Component Interaction Diagrams

### Scenario: Priority Update

```
Doctor: "This patient needs emergency surgery — update from P3 to P5"

Frontend                    Flask API                 PatientService             Heap              PostgreSQL
   │                            │                           │                    │                    │
   │ PUT /patients/id/priority   │                           │                    │                    │
   │ {new_priority: 5}           │                           │                    │                    │
   ├─────────────────────────────►                           │                    │                    │
   │                             │ update_priority()         │                    │                    │
   │                             ├──────────────────────────►                     │                    │
   │                             │                           │ find patient       │                    │
   │                             │                           ├─ O(n) scan        │                    │
   │                             │                           │                    │                    │
   │                             │                           │ update_priority()  │                    │
   │                             │                           ├──────────────────►                     │
   │                             │                           │                    │ bubble_up()        │
   │                             │                           │                    ├─ O(log n) move    │
   │                             │                           │                    │◄──────────────────┤
   │                             │                           │                    │                    │
   │                             │                           │ UPDATE patients    │                    │
   │                             │                           │ SET priority = 5   │                    │
   │                             │                           ├───────────────────────────────────────►
   │                             │                           │                    │                    │ COMMIT
   │                             │                           │                    │                    │◄───────
   │                             │                           │ INSERT audit_log   │                    │
   │                             │                           ├───────────────────────────────────────►
   │                             │                           │                    │                    │ COMMIT
   │                             │                           │                    │                    │◄───────
   │                             │ return success            │                    │                    │
   │◄─────────────────────────────┤◄──────────────────────────┤                    │                    │
   │ {success: true}              │                           │                    │                    │
   │ Re-render queue ────────────►│                           │                    │                    │
   │                              │ GET /patients             │                    │                    │
   │                              ├──────────────────────────►│                    │                    │
   │                              │                           │ get_waiting_queue()│                    │
   │                              │                           ├────────────────────► heap.to_sorted_list()
   │                              │                           │                    │                    │
   │                              │                           │ return list        │                    │
   │                              │ return list              │◄────────────────────┤                    │
   │◄─────────────────────────────┤◄──────────────────────────┤                    │                    │
   │ [P5 Rajesh, P5 Updated,      │                           │                    │                    │
   │  P4 Arjun, ...]              │                           │                    │                    │
   │                              │                           │                    │                    │
```

---

## Time Complexity Analysis

| Operation | Traditional List | Sorted List | Binary Heap |
|-----------|-----------------|-------------|------------|
| Insert | O(1) | O(n) | **O(log n)** |
| Extract Max | O(n) | O(1) | **O(log n)** |
| Find | O(n) | O(n) | **O(n)** |
| Update Priority | O(n) | O(n) | **O(n) + O(log n) reheapify** |
| Build | O(1) | O(n log n) | **O(n)** |

**For 1000 waiting patients:**
- Extract top 10 patients: 10 × O(log 1000) ≈ 10 × 10 = 100 ops vs. O(n) = 1000 ops ✓
- Rebuild from DB: O(n) = 1000 insertions × O(log n) ≈ 10,000 ops vs. O(n²) = 1,000,000 ops ✓

---

## Failure Recovery Scenarios

### Scenario 1: Connection Pool Exhaustion
```
Problem: forgot try/finally, connection never released
Result: After 10 failed requests, pool(maxconn=10) is exhausted
       11th request → deadlock

Prevention: Every DB operation wrapped in try/finally:
  conn = get_conn()
  try:
      execute queries
  finally:
      release_conn(conn)  ← ALWAYS called
```

### Scenario 2: Gemini API Timeout
```
Problem: Network issue, Gemini doesn't respond
Result: suggest_priority() hangs for 30+ seconds

Prevention: suggest_priority() catches ALL exceptions:
  try:
      response = _model.generate_content(prompt)
      return parse_json(response)
  except Exception as e:
      return FALLBACK  ← Priority 3 (Moderate)
```

### Scenario 3: Heap-DB Mismatch
```
Problem: Bug causes heap & DB to diverge
Result: Admit next may return wrong patient

Prevention: rebuild_heap() on every app startup:
  1. Truncate in-memory heap
  2. SELECT * FROM patients WHERE status='waiting'
  3. Re-insert all rows
  
Frequency: Every server restart
Time: <100ms for 1000 patients
```

---

**End of Architecture Documentation**
