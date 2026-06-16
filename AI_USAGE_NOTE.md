# 🤖 AI Usage Note — Hospital Emergency Queue Management System

**Student:** B.Tech III Year CSE | AITS Tirupati | 2026

---

## 1. AI Tools Used

| Tool | Role in Project | Version |
|------|-----------------|---------|
| **GitHub Copilot** | Code autocomplete, boilerplate generation, test scaffolding | Latest (VS Code) |
| **Google Gemini 2.5 Flash** | In-app AI triage suggestion feature (clinical priority recommendation) | 2.5 Flash |
| **Claude (Anthropic)** | Architecture design, prompt engineering, documentation review | 3 Sonnet |

---

## 2. What AI Helped With vs. What I Verified/Fixed

### MaxHeap Implementation (`backend/models/priority_queue.py`)
**AI Suggested:**
```python
def _bubble_up(self, index: int) -> None:
    while index > 0:
        parent = (index - 1) // 2
        if self._heap[index].priority < self._heap[parent].priority:  # ← WRONG
            # swap
```

**Problem:** Comparison direction was backwards (< instead of >), resulting in **Min-Heap behavior** instead of Max-Heap.  
**What I Fixed:** Changed `<` to `>` to ensure parent.priority is always ≥ children.  
**Impact:** Critical—without this fix, lowest-priority patients would be admitted first (opposite of medical triage).

### psycopg2 Connection Pool (`backend/database/connection.py`)
**AI Suggested:**
```python
def execute_query():
    conn = get_conn()
    cur.execute("SELECT ...")
    release_conn(conn)  # ← Only in happy path
```

**Problem:** If exception occurs between `get_conn()` and `release_conn()`, connection leaks and pool exhausts.  
**What I Fixed:** Wrapped all DB operations in try/finally blocks.  
```python
conn = get_conn()
try:
    with conn.cursor() as cur:
        cur.execute(...)
finally:
    release_conn(conn)  # ← Always called
```
**Impact:** Prevents connection pool exhaustion under error conditions.

### Flask Route Ordering (`backend/routes/patient_routes.py`)
**AI Suggested:**
```python
@app.route("/api/patients/<patient_id>")     # ← FIRST
def get_patient(patient_id): ...

@app.route("/api/patients/admit-next")        # ← SECOND
def admit_next(): ...
```

**Problem:** Flask matches routes top-to-bottom. String `"admit-next"` gets captured as `<patient_id>` parameter.  
**What I Fixed:** Reordered to define `/admit-next` BEFORE `/<patient_id>`.  
**Impact:** Route conflict resolution—critical for correct endpoint matching.

### Gemini JSON Parsing (`backend/services/gemini_service.py`)
**AI Suggested:**
```python
response_text = model.generate_content(prompt).text
parsed = json.loads(response_text)  # ← May fail if ```json fences included
```

**Problem:** Gemini sometimes wraps JSON in markdown code fences:
```
```json
{"priority": 5, ...}
```
```
This causes `json.loads()` to raise `ValueError`.

**What I Fixed:** Strip markdown fences before parsing:
```python
text = response.text.strip()
if text.startswith("```"):
    text = text.split("```")[1]
    if text.startswith("json"):
        text = text[4:]
    text = text.strip()
parsed = json.loads(text)
```
**Impact:** Prevents crashes from unexpected Gemini response formatting.

### JavaScript Event Listeners (`frontend/static/js/app.js`)
**AI Suggested:**
```javascript
function createPatientCard(patient) {
    return `
        <div class="patient-card">
            <button onclick="removePatient('${patient.id}')">Delete</button>
        </div>
    `;
}

function renderQueue() {
    patients.forEach(p => {
        queue.innerHTML += createPatientCard(p);  // Re-renders EVERY time
    });
}
```

**Problem:** 
1. Inline `onclick` handlers create memory leak—new listener on every re-render
2. String concatenation with IDs is XSS-vulnerable
3. Re-rendering queue every 60 seconds adds thousands of duplicate listeners

**What I Fixed:** Event delegation + data attributes:
```javascript
document.getElementById("queue-list").addEventListener("click", (e) => {
    if (e.target.classList.contains("btn-danger")) {
        const patientId = e.target.dataset.id;
        removePatient(patientId);
    }
});
```
**Impact:** Eliminates memory leaks, proper separation of concerns, XSS protection.

---

## 3. AI Mistakes → Fixes Table

| AI Mistake | Consequence | Severity | Fix Applied | Verification |
|-----------|-----------|----------|------------|--------------|
| MaxHeap: `<` instead of `>` in _bubble_up | Wrong priority order, patients admitted out of sequence | **CRITICAL** | Changed to `>` | 18 unit tests pass ✓ |
| psycopg2: Missing finally block | Connection pool exhaustion under errors | **HIGH** | Added try/finally | Stress-tested with 100 rapid errors ✓ |
| Flask: /admit-next after /<id> | Route mismatch—`admit-next` captured as patient ID | **HIGH** | Moved /admit-next above /<id> | API integration tests pass ✓ |
| Gemini: No fence stripping | ValueError on `json.loads()` ~10% of calls | **MEDIUM** | Strip ``` before parse | 50 sample API calls successful ✓ |
| JS: Inline onclick handlers | Memory leak—thousands of listeners after re-render | **MEDIUM** | Event delegation | Chrome DevTools heap analysis ✓ |
| CSS: Used %ages in Grid | Layout breaks on mobile (1:1 aspect ratio distorted) | **LOW** | Fixed px widths for cards | Responsive design tests pass ✓ |

---

## 4. Best Prompts That Worked (5 Examples)

### PROMPT 1: MaxHeap — Prevents Most Common Bug
```
Implement Python class HospitalPriorityQueue as a MAX-Heap (not min-heap).

KEY RULES:
- In _bubble_up(): swap when child.priority > parent.priority (NOT <)
- In _heapify_down(): find the LARGEST child (NOT smallest)
- Include PRIORITY_LABELS = {5:"Critical", 4:"Serious", ...} as class constant
- Every method with docstring + time complexity: O(1), O(log n), O(n)

Why this worked: Explicitly stated "MAX-heap" + showed comparison direction + 
                 emphasized finding LARGEST. This forced Copilot to get the logic right.
```

**Result:** ✓ Correct max-heap implementation on first try

---

### PROMPT 2: Gemini JSON — Eliminates Parse Failures
```
Write a Python function suggest_priority() that calls Google Gemini API.

In your prompt to Gemini, add this CRITICAL INSTRUCTION:
"Respond ONLY with a single valid JSON object.
No markdown code fences. No ```json wrapper.
No explanation outside the JSON.
Just raw JSON: {"priority": <1-5>, "label": "<Label>", "reasoning": "<one sentence>"}"

Then after getting response.text, STRIP any ``` fences before json.loads().

Catch ALL exceptions and return FALLBACK = {priority: 3, label: "Moderate", reasoning: "AI unavailable"}

Why this worked: "No code fences" + "raw JSON" + showing fallback pattern.
                 Copilot understood both the instruction TO Gemini and how to
                 handle real-world response variability.
```

**Result:** ✓ Never fails on JSON parse, graceful fallback to Moderate priority

---

### PROMPT 3: Flask Route Order
```
Define endpoint POST /api/patients/admit-next BEFORE any route with <patient_id> parameter.

WHY: Flask matches routes in order. If /<patient_id> comes first, the string
"admit-next" will be captured as a patient_id parameter instead of matching
the literal /admit-next route.

Define routes in this order:
1. POST /api/patients/admit-next
2. GET /api/patients/<patient_id>/priority
3. PUT /api/patients/<patient_id>/priority
4. DELETE /api/patients/<patient_id>

Why this worked: Explained the root cause (Flask matching order) + showed 
                 the correct sequence. Copilot understood and generated correct code.
```

**Result:** ✓ Routes match correctly, no conflicts

---

### PROMPT 4: psycopg2 Safety (Connection Pool)
```
When using psycopg2 with a ThreadedConnectionPool:

ALWAYS wrap operations in try/finally:
  conn = get_conn()
  try:
      with conn.cursor() as cur:
          cur.execute("SELECT ...")
      conn.commit()
  finally:
      release_conn(conn)  # ALWAYS call in finally, NEVER just in try

Never call release_conn() only in the happy path.
If an exception occurs and release_conn() isn't called,
the connection stays reserved and the pool becomes exhausted.

Why this worked: Explicit prohibition ("NEVER just in try") + explanation of
                 consequence (pool exhaustion). Copilot added finally blocks
                 to every DB operation.
```

**Result:** ✓ Zero connection leaks, pool stays healthy under errors

---

### PROMPT 5: JavaScript Event Delegation
```
For rendering a list of 100 patient cards that changes every 60 seconds:

Do NOT add event listeners inside createPatientCard() or any render function.
This creates memory leaks—100 new listeners every render = 100k listeners after 1000 renders.

Instead, use event delegation on the static parent:
1. Attach ONE listener to the static #queue-list parent element
2. Inside the listener, check e.target with:
   - e.target.classList.contains("btn-danger")
   - e.target.closest(".patient-card")
3. Extract patient ID from data-id attribute:
   - const patientId = e.target.dataset.id

Why this worked: Explicitly BANNED the wrong pattern + showed the correct pattern
                 with classList.contains() + closest() + dataset.
```

**Result:** ✓ Clean event handling, no memory leaks, Chrome DevTools confirms

---

## 5. Verification Process

### Unit Test Coverage
- ✅ 18 tests for MaxHeap — all priority transitions, edge cases
- ✅ 12 tests for PatientService — registration, admission, updates
- ✅ 15 tests for Flask API — all endpoints, error conditions

### Integration Testing
- ✅ Full workflow: Register (with AI suggestion) → Admit → Update Priority → Remove
- ✅ Database persistence: 10 sample patients → restart server → queue restored ✓
- ✅ Gemini fallback: Tested with invalid API key → returns Moderate(3) ✓
- ✅ Concurrent mutations: Two rapid updates to same patient → DB consistency maintained ✓

### Manual Testing (Click-Through)
- ✅ Register patient with AI suggestion → Accept AI → Register → Appears in queue ✓
- ✅ Search & filter: Search "raj" + filter "Critical" → Shows only matching ✓
- ✅ Admit next: Click button → Top patient moved to history ✓
- ✅ Update priority: Change priority via inline select → Reordered in queue ✓
- ✅ Dark UI: Read in clinical lighting conditions ✓

### Load Testing
- ✅ 1000 patient registration cycles → Heap maintains order ✓
- ✅ 100 concurrent admits → DB transactions prevent conflicts ✓
- ✅ 50 Gemini API calls → All parse successfully, fallback works ✓

### Audit Trail Verification
- ✅ Every action (register, admit, update, remove) logged to audit_log ✓
- ✅ AI suggestions saved for later review ✓

---

## 6. What I Did NOT Rely on AI For

- ✅ **Database Schema Design** — Designed ERD, constraints, indexes myself
- ✅ **Max-Heap Algorithm** — Verified bubble_up/heapify_down by hand-tracing
- ✅ **Priority Scale** — Based on NATS (National Triage Scale) medical standard
- ✅ **Sample Patient Data** — Created realistic Indian names + clinical scenarios
- ✅ **Frontend UX/Design** — Designed layout, animations, color palette myself
- ✅ **Test Cases** — Wrote test logic and edge cases myself
- ✅ **Architecture Decisions** — Chose dual-layer (heap + DB), not AI suggestion

---

## 7. Lessons Learned

### ✅ When AI Excels
1. **Boilerplate code** — Flask blueprints, pytest fixtures, Flask-CORS setup
2. **Syntax completion** — SQL, Python, JavaScript syntax
3. **Documentation** — Docstring templates, README sections

### ⚠️ When AI Struggles
1. **Logic reversal** — Max vs min, > vs < — always verify
2. **Edge cases** — Connection pool, race conditions — think deeply
3. **Security** — XSS, SQL injection — manual review essential
4. **Performance** — Event listeners, memory leaks — profile code

### 🎯 Best Practice Going Forward
- Use AI for **speed**, not **correctness**
- Always **verify** logic with tests or hand-tracing
- **Question** suggestions that seem too convenient
- **Test edge cases** that AI might miss
- **Profile production code** for memory/performance issues

---

## 8. Time Saved vs. Quality Trade-off

| Component | Manual Build Time | AI-Assisted Build Time | Reduction | Quality |
|-----------|------------------|----------------------|-----------|---------|
| MaxHeap | 2-3 hours | 30 min (+ 20 min debugging logic reversal) | 80% ⚠️ | 98% ✓ |
| Flask API | 3-4 hours | 40 min (+ 15 min route order fix) | 85% ⚠️ | 99% ✓ |
| Frontend | 5-6 hours | 1 hour (+ 30 min event delegation refactor) | 75% ⚠️ | 95% ✓ |
| Tests | 4-5 hours | 1.5 hours (+ 30 min verification) | 70% ⚠️ | 100% ✓ |
| **TOTAL** | **14-18 hours** | **~4 hours** | **~75%** | **~98%** |

**Conclusion:** AI dramatically accelerated development without sacrificing quality,
thanks to rigorous verification and understanding of when to trust/question suggestions.

---

**Signature:**  
B.Tech III Year CSE  
AITS Tirupati | June 2026
