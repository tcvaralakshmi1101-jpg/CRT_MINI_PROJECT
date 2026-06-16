import pytest
import json

def test_health_endpoint_returns_ok(client, clean_db):
    """Test GET /api/health returns 200 with status ok."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert "queue_size" in data

def test_register_patient_returns_201(client, clean_db, make_patient_dict):
    """Test POST /api/patients returns 201 on success."""
    data = make_patient_dict()
    resp = client.post("/api/patients", json=data)
    assert resp.status_code == 201
    result = resp.get_json()
    assert result["success"] is True
    assert "id" in result["patient"]
    assert result["patient"]["priority_label"] == "Serious"

def test_register_empty_name_returns_400(client, clean_db, make_patient_dict):
    """Test POST /api/patients returns 400 for empty name."""
    data = make_patient_dict(name="")
    resp = client.post("/api/patients", json=data)
    assert resp.status_code == 400
    assert "error" in resp.get_json()

def test_register_invalid_age_returns_400(client, clean_db, make_patient_dict):
    """Test POST /api/patients returns 400 for invalid age."""
    data = make_patient_dict(age=200)
    resp = client.post("/api/patients", json=data)
    assert resp.status_code == 400

def test_register_priority_out_of_range_returns_400(client, clean_db, make_patient_dict):
    """Test POST /api/patients returns 400 for priority > 5."""
    data = make_patient_dict(priority=6)
    resp = client.post("/api/patients", json=data)
    assert resp.status_code == 400

def test_get_patients_empty_returns_empty_list(client, clean_db):
    """Test GET /api/patients returns empty list when no patients."""
    resp = client.get("/api/patients")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["patients"] == []
    assert data["count"] == 0

def test_get_patients_sorted_by_priority(client, clean_db, make_patient_dict):
    """Test GET /api/patients returns patients sorted by priority desc."""
    client.post("/api/patients", json=make_patient_dict(priority=2))
    client.post("/api/patients", json=make_patient_dict(priority=5))
    
    resp = client.get("/api/patients")
    data = resp.get_json()
    assert data["patients"][0]["priority"] == 5
    assert data["patients"][1]["priority"] == 2

def test_admit_next_returns_highest_priority(client, clean_db, make_patient_dict):
    """Test POST /api/patients/admit-next returns highest priority patient."""
    client.post("/api/patients", json=make_patient_dict(priority=2))
    client.post("/api/patients", json=make_patient_dict(priority=5))
    
    resp = client.post("/api/patients/admit-next")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["admitted"]["priority"] == 5
    assert data["remaining_in_queue"] == 1

def test_admit_next_on_empty_queue_returns_404(client, clean_db):
    """Test POST /api/patients/admit-next returns 404 on empty queue."""
    resp = client.post("/api/patients/admit-next")
    assert resp.status_code == 404
    assert "error" in resp.get_json()

def test_update_priority_success(client, clean_db, make_patient_dict):
    """Test PUT /api/patients/<id>/priority updates priority."""
    # Register patient
    reg_resp = client.post("/api/patients", json=make_patient_dict(priority=2))
    patient_id = reg_resp.get_json()["patient"]["id"]
    
    # Update priority
    update_resp = client.put(f"/api/patients/{patient_id}/priority", 
                             json={"new_priority": 5})
    assert update_resp.status_code == 200
    assert update_resp.get_json()["success"] is True
    
    # Verify in queue
    get_resp = client.get("/api/patients")
    patients = get_resp.get_json()["patients"]
    assert patients[0]["priority"] == 5

def test_update_priority_invalid_id_returns_404(client, clean_db):
    """Test PUT /api/patients/<nonexistent>/priority returns 404."""
    resp = client.put("/api/patients/nonexistent-id/priority", 
                      json={"new_priority": 3})
    assert resp.status_code == 404

def test_delete_patient_success(client, clean_db, make_patient_dict):
    """Test DELETE /api/patients/<id> removes patient."""
    # Register patient
    reg_resp = client.post("/api/patients", json=make_patient_dict())
    patient_id = reg_resp.get_json()["patient"]["id"]
    
    # Delete
    del_resp = client.delete(f"/api/patients/{patient_id}")
    assert del_resp.status_code == 200
    assert del_resp.get_json()["success"] is True
    
    # Verify removed from queue
    get_resp = client.get("/api/patients")
    assert get_resp.get_json()["count"] == 0

def test_delete_invalid_id_returns_404(client, clean_db):
    """Test DELETE /api/patients/<nonexistent> returns 404."""
    resp = client.delete("/api/patients/nonexistent-id")
    assert resp.status_code == 404

def test_stats_counts_match_registrations(client, clean_db, make_patient_dict):
    """Test GET /api/stats counts are correct."""
    client.post("/api/patients", json=make_patient_dict(priority=5))
    client.post("/api/patients", json=make_patient_dict(priority=5))
    client.post("/api/patients", json=make_patient_dict(priority=2))
    
    resp = client.get("/api/stats")
    stats = resp.get_json()
    assert stats["total"] == 3
    assert stats["by_priority"]["5"] == 2
    assert stats["by_priority"]["2"] == 1

def test_history_reflects_admitted_patients(client, clean_db, make_patient_dict):
    """Test GET /api/history returns admitted patients."""
    # Register patient
    reg_resp = client.post("/api/patients", json=make_patient_dict())
    
    # Admit
    client.post("/api/patients/admit-next")
    
    # Check history
    hist_resp = client.get("/api/history")
    data = hist_resp.get_json()
    assert data["count"] == 1
    assert "admitted_at" in data["history"][0]
