const BASE = "";

const PRIORITY_CONFIG = {
    5: { label: "Critical", color: "#FF3B3B", cls: "p5" },
    4: { label: "Serious", color: "#FF8C00", cls: "p4" },
    3: { label: "Moderate", color: "#FFD700", cls: "p3" },
    2: { label: "Mild", color: "#4CAF50", cls: "p2" },
    1: { label: "Minor", color: "#2196F3", cls: "p1" }
};

let aiSuggestedData = null;
let historyVisible = false;
let historyCount = 0;

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll("\"", "&quot;")
        .replaceAll("'", "&#39;");
}

function priorityLabel(priority) {
    return (PRIORITY_CONFIG[priority] || PRIORITY_CONFIG[3]).label;
}

function setHistoryButtonText(count) {
    historyCount = count;
    const button = document.getElementById("btn-toggle-history");
    button.textContent = historyVisible
        ? `Hide Admitted Today (${count})`
        : `Show Admitted Today (${count})`;
}

function showToast(message, isError = false) {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.classList.toggle("error", isError);
    toast.style.display = "block";
    setTimeout(() => {
        toast.style.display = "none";
    }, 3000);
}

function formatWaitTime(arrivalISO) {
    const arrival = new Date(arrivalISO);
    const now = new Date();
    const diffMins = Math.floor((now - arrival) / 60000);

    if (diffMins < 60) {
        return `${diffMins}m ago`;
    }

    const hours = Math.floor(diffMins / 60);
    const mins = diffMins % 60;
    return `${hours}h ${mins}m ago`;
}

function createPatientCard(patient) {
    const priorityInfo = PRIORITY_CONFIG[patient.priority] || PRIORITY_CONFIG[3];
    const aiDiffBadge = patient.ai_suggested_priority > 0 &&
        patient.ai_suggested_priority !== patient.priority
        ? `<span class="ai-diff-badge">AI: P${patient.ai_suggested_priority}</span>`
        : "";
    const waitAlert = patient.needs_attention
        ? `<span class="ai-diff-badge" style="background:#DC2626;">Long wait: ${patient.wait_minutes}m</span>`
        : "";

    const arrivalTime = new Date(patient.arrival_time);
    const timeStr = arrivalTime.toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: true
    });
    const waitTime = formatWaitTime(patient.arrival_time);

    return `
        <div class="patient-card priority-${patient.priority}" data-id="${escapeHtml(patient.id)}">
            <div class="priority-badge ${priorityInfo.cls}">
                P${patient.priority} - ${priorityInfo.label} ${aiDiffBadge} ${waitAlert}
            </div>
            <div style="font-weight: 600; margin-bottom: 4px;">${escapeHtml(patient.name)}</div>
            <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 4px;">
                Age: ${escapeHtml(patient.age)} | Gender: ${escapeHtml(patient.gender)}
            </div>
            <div style="font-size: 0.85rem; margin-bottom: 8px; color: var(--text);">
                <strong>Condition:</strong> ${escapeHtml(patient.condition)}
            </div>
            <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 8px;">
                Arrived: ${timeStr} (${waitTime})
            </div>
            <div style="font-size: 0.85rem; margin-bottom: 8px;">
                <label for="priority-select-${escapeHtml(patient.id)}">Update Priority:</label>
                <select class="inline-priority-select" id="priority-select-${escapeHtml(patient.id)}" data-id="${escapeHtml(patient.id)}" style="width: 100%; padding: 4px; margin-top: 4px;">
                    <option value="5" ${patient.priority === 5 ? "selected" : ""}>5 - Critical</option>
                    <option value="4" ${patient.priority === 4 ? "selected" : ""}>4 - Serious</option>
                    <option value="3" ${patient.priority === 3 ? "selected" : ""}>3 - Moderate</option>
                    <option value="2" ${patient.priority === 2 ? "selected" : ""}>2 - Mild</option>
                    <option value="1" ${patient.priority === 1 ? "selected" : ""}>1 - Minor</option>
                </select>
                <button type="button" class="btn-update-priority" data-id="${escapeHtml(patient.id)}">Update</button>
            </div>
            <button type="button" class="btn-danger" data-id="${escapeHtml(patient.id)}" data-name="${escapeHtml(patient.name)}">Remove</button>
        </div>
    `;
}

async function renderQueue() {
    try {
        const resp = await fetch(`${BASE}/api/patients`);
        if (!resp.ok) throw new Error("Failed to fetch queue");

        const data = await resp.json();
        let patients = data.patients || [];

        const searchTerm = document.getElementById("search-input").value.toLowerCase();
        if (searchTerm) {
            patients = patients.filter((patient) =>
                patient.name.toLowerCase().includes(searchTerm)
            );
        }

        const priorityFilter = document.getElementById("filter-priority").value;
        if (priorityFilter) {
            patients = patients.filter((patient) => String(patient.priority) === priorityFilter);
        }

        const queueList = document.getElementById("queue-list");
        const emptyMsg = document.getElementById("queue-empty-msg");

        if (patients.length === 0) {
            queueList.innerHTML = "";
            emptyMsg.style.display = "block";
        } else {
            queueList.innerHTML = patients.map(createPatientCard).join("");
            emptyMsg.style.display = "none";
        }

        document.getElementById("queue-count-badge").textContent = patients.length;
        document.getElementById("header-queue-count").textContent = data.count ?? 0;
    } catch (err) {
        console.error("renderQueue error:", err);
        showToast("Failed to load queue", true);
    }
}

async function getAISuggestion() {
    const name = document.getElementById("inp-name").value.trim();
    const age = document.getElementById("inp-age").value.trim();
    const condition = document.getElementById("inp-condition").value.trim();

    if (!name || !age || !condition) {
        showToast("Fill name, age, and condition first", true);
        return;
    }

    const btn = document.getElementById("btn-ai-suggest");
    btn.disabled = true;
    btn.textContent = "Loading...";

    try {
        const resp = await fetch(`${BASE}/api/suggest-priority`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, age: parseInt(age, 10), condition })
        });

        if (!resp.ok) {
            const error = await resp.json();
            showToast(error.error || "AI suggestion failed", true);
            return;
        }

        const result = await resp.json();
        aiSuggestedData = {
            priority: result.priority,
            label: result.label,
            reasoning: result.reasoning
        };

        document.getElementById("ai-priority-text").textContent = `P${result.priority} - ${result.label}`;
        document.getElementById("ai-reasoning-text").textContent = `Reasoning: ${result.reasoning}`;
        document.getElementById("ai-suggestion-box").classList.remove("hidden");
        document.getElementById("btn-accept-ai").classList.remove("selected");
    } catch (err) {
        console.error("getAISuggestion error:", err);
        showToast("Error getting AI suggestion", true);
    } finally {
        btn.disabled = false;
        btn.textContent = "Get AI Suggestion";
    }
}

function acceptAISuggestion() {
    if (!aiSuggestedData) return;

    document.getElementById("final-priority").value = aiSuggestedData.priority;
    document.getElementById("final-ai-suggested").value = aiSuggestedData.priority;
    document.getElementById("final-ai-reasoning").value = aiSuggestedData.reasoning;
    document.getElementById("override-select").value = aiSuggestedData.priority;

    document.getElementById("btn-accept-ai").classList.add("selected");
    document.getElementById("priority-display-line").textContent =
        `Selected: P${aiSuggestedData.priority} - ${aiSuggestedData.label} (AI-suggested)`;
}

function onOverrideChange() {
    const priority = document.getElementById("override-select").value;

    if (!priority) {
        document.getElementById("priority-display-line").textContent = "Select a priority above";
        document.getElementById("final-priority").value = "";
        document.getElementById("final-ai-suggested").value = "0";
        document.getElementById("final-ai-reasoning").value = "";
        return;
    }

    document.getElementById("final-priority").value = priority;
    document.getElementById("final-ai-suggested").value = "0";
    document.getElementById("final-ai-reasoning").value = "";
    document.getElementById("btn-accept-ai").classList.remove("selected");

    const label = priorityLabel(priority);
    document.getElementById("priority-display-line").textContent = `Selected: P${priority} - ${label}`;
}

async function registerPatient(e) {
    e.preventDefault();

    const name = document.getElementById("inp-name").value.trim();
    const age = document.getElementById("inp-age").value.trim();
    const gender = document.getElementById("inp-gender").value;
    const condition = document.getElementById("inp-condition").value.trim();
    const priority = document.getElementById("final-priority").value;
    const aiSuggested = parseInt(document.getElementById("final-ai-suggested").value, 10) || 0;
    const aiReasoning = document.getElementById("final-ai-reasoning").value;

    const errorDiv = document.getElementById("form-error");
    errorDiv.classList.add("hidden");

    if (!name || !age || !gender || !condition || !priority) {
        showError("All fields are required");
        return;
    }

    if (parseInt(age, 10) < 1 || parseInt(age, 10) > 120) {
        showError("Age must be between 1 and 120");
        return;
    }

    const btn = document.getElementById("btn-register");
    btn.disabled = true;
    btn.textContent = "Registering...";

    try {
        const resp = await fetch(`${BASE}/api/patients`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                name,
                age: parseInt(age, 10),
                gender,
                condition,
                priority: parseInt(priority, 10),
                ai_suggested_priority: aiSuggested,
                ai_reasoning: aiReasoning
            })
        });

        if (!resp.ok) {
            const error = await resp.json();
            showError(error.error || "Registration failed");
            return;
        }

        const result = await resp.json();
        showToast(`Registered ${result.patient.name} as P${result.patient.priority}`);

        await renderQueue();
        await updateStats();
        await renderHistory();
        resetForm();
    } catch (err) {
        console.error("registerPatient error:", err);
        showError("Error registering patient");
    } finally {
        btn.disabled = false;
        btn.textContent = "Register Patient";
    }
}

async function admitNextPatient() {
    const btn = document.getElementById("btn-admit-next");
    btn.disabled = true;
    btn.textContent = "Admitting...";

    try {
        const resp = await fetch(`${BASE}/api/patients/admit-next`, {
            method: "POST"
        });

        if (!resp.ok) {
            const error = await resp.json();
            showToast(error.error || "Failed to admit", true);
            return;
        }

        const result = await resp.json();
        const patient = result.admitted;
        showToast(`Admitted ${patient.name} (P${patient.priority} ${priorityLabel(patient.priority)})`);

        await renderQueue();
        await updateStats();
        await renderHistory();
    } catch (err) {
        console.error("admitNextPatient error:", err);
        showToast("Error admitting patient", true);
    } finally {
        btn.disabled = false;
        btn.textContent = "Admit Next Patient";
    }
}

async function updatePatientPriority(patientId, newPriority) {
    try {
        const resp = await fetch(`${BASE}/api/patients/${patientId}/priority`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ new_priority: newPriority })
        });

        if (!resp.ok) {
            const error = await resp.json();
            showToast(error.error || "Update failed", true);
            return;
        }

        showToast("Priority updated");
        await renderQueue();
        await updateStats();
    } catch (err) {
        console.error("updatePatientPriority error:", err);
        showToast("Error updating priority", true);
    }
}

async function removePatient(patientId, patientName) {
    if (!confirm(`Remove ${patientName} from queue?`)) return;

    try {
        const resp = await fetch(`${BASE}/api/patients/${patientId}`, {
            method: "DELETE"
        });

        if (!resp.ok) {
            const error = await resp.json();
            showToast(error.error || "Remove failed", true);
            return;
        }

        showToast(`Removed ${patientName} from queue`);
        await renderQueue();
        await updateStats();
    } catch (err) {
        console.error("removePatient error:", err);
        showToast("Error removing patient", true);
    }
}

async function updateStats() {
    try {
        const resp = await fetch(`${BASE}/api/stats`);
        if (!resp.ok) throw new Error("Failed to fetch stats");

        const stats = await resp.json();
        const byPriority = stats.by_priority || {};

        document.getElementById("stat-total").querySelector(".stat-value").textContent = stats.total ?? 0;
        document.getElementById("stat-critical").querySelector(".stat-value").textContent = byPriority["5"] ?? 0;
        document.getElementById("stat-serious").querySelector(".stat-value").textContent = byPriority["4"] ?? 0;
        document.getElementById("stat-moderate").querySelector(".stat-value").textContent = byPriority["3"] ?? 0;
        document.getElementById("stat-mild-minor").querySelector(".stat-value").textContent =
            (byPriority["2"] ?? 0) + (byPriority["1"] ?? 0);
        document.getElementById("stat-avg-wait").querySelector(".stat-value").textContent =
            `${Number(stats.average_wait_minutes || 0).toFixed(0)}m`;
        document.getElementById("stat-treated").querySelector(".stat-value").textContent = stats.treated_today ?? 0;
    } catch (err) {
        console.error("updateStats error:", err);
    }
}

async function renderHistory() {
    try {
        const resp = await fetch(`${BASE}/api/history`);
        if (!resp.ok) throw new Error("Failed to fetch history");

        const data = await resp.json();
        const historyList = document.getElementById("history-list");

        if (data.count === 0) {
            historyList.innerHTML = "<div style='color: var(--text-muted); text-align: center; padding: 16px;'>No patients admitted today</div>";
        } else {
            historyList.innerHTML = data.history.map((patient) => {
                const admittedTime = new Date(patient.admitted_at).toLocaleTimeString("en-US", {
                    hour: "2-digit",
                    minute: "2-digit",
                    hour12: true
                });

                return `
                    <div class="history-card">
                        <strong>${escapeHtml(patient.name)}</strong> - P${patient.priority} ${priorityLabel(patient.priority)}
                        <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 2px;">
                            Admitted: ${admittedTime}
                        </div>
                    </div>
                `;
            }).join("");
        }

        setHistoryButtonText(data.count || 0);
    } catch (err) {
        console.error("renderHistory error:", err);
    }
}

function showError(message) {
    const errorDiv = document.getElementById("form-error");
    errorDiv.textContent = message;
    errorDiv.classList.remove("hidden");
    setTimeout(() => {
        errorDiv.classList.add("hidden");
    }, 4000);
}

function resetForm() {
    document.getElementById("inp-name").value = "";
    document.getElementById("inp-age").value = "";
    document.getElementById("inp-gender").value = "";
    document.getElementById("inp-condition").value = "";
    document.getElementById("override-select").value = "";
    document.getElementById("ai-suggestion-box").classList.add("hidden");
    document.getElementById("final-priority").value = "";
    document.getElementById("final-ai-suggested").value = "0";
    document.getElementById("final-ai-reasoning").value = "";
    document.getElementById("priority-display-line").textContent = "Select a priority above";
    document.getElementById("form-error").classList.add("hidden");
    aiSuggestedData = null;
}

function toggleHistory() {
    historyVisible = !historyVisible;
    const historyList = document.getElementById("history-list");

    if (historyVisible) {
        historyList.classList.remove("hidden");
    } else {
        historyList.classList.add("hidden");
    }

    setHistoryButtonText(historyCount);
}

document.addEventListener("DOMContentLoaded", async () => {
    document.getElementById("registration-form").style.display = "block";

    document.getElementById("btn-ai-suggest").addEventListener("click", getAISuggestion);
    document.getElementById("btn-accept-ai").addEventListener("click", acceptAISuggestion);
    document.getElementById("override-select").addEventListener("change", onOverrideChange);
    document.getElementById("registration-form").addEventListener("submit", registerPatient);
    document.getElementById("btn-admit-next").addEventListener("click", admitNextPatient);
    document.getElementById("btn-toggle-history").addEventListener("click", toggleHistory);

    document.getElementById("search-input").addEventListener("input", renderQueue);
    document.getElementById("filter-priority").addEventListener("change", renderQueue);

    document.getElementById("queue-list").addEventListener("click", (e) => {
        if (e.target.classList.contains("btn-update-priority")) {
            const patientId = e.target.dataset.id;
            const selectEl = document.querySelector(`select[data-id="${CSS.escape(patientId)}"]`);
            const newPriority = parseInt(selectEl.value, 10);
            updatePatientPriority(patientId, newPriority);
        }

        if (e.target.classList.contains("btn-danger")) {
            const patientId = e.target.dataset.id;
            const patientName = e.target.dataset.name;
            removePatient(patientId, patientName);
        }
    });

    await renderQueue();
    await updateStats();
    await renderHistory();

    setInterval(async () => {
        await renderQueue();
        await updateStats();
    }, 60000);
});
