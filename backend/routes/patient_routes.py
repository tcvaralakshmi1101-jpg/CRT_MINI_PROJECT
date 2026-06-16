from flask import Blueprint, jsonify, request
from backend.services import patient_service as svc
from backend.services.gemini_service import suggest_priority

patient_bp = Blueprint("patients", __name__)

@patient_bp.route("/suggest-priority", methods=["POST"])
def api_suggest_priority():
    """Use Gemini AI to suggest priority based on patient symptoms."""
    data = request.get_json() or {}
    name      = data.get("name", "").strip()
    age_str   = data.get("age", "")
    condition = data.get("condition", "").strip()
    
    if not name:
        return jsonify({"error": "Name is required"}), 400
    if not condition:
        return jsonify({"error": "Condition is required"}), 400
    
    try:
        age = int(age_str)
        if not 1 <= age <= 120:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({"error": "Age must be an integer between 1 and 120"}), 400
    
    result = suggest_priority(name, age, condition)
    return jsonify(result), 200

@patient_bp.route("/patients", methods=["POST"])
def api_register_patient():
    """Register a new patient with priority."""
    data = request.get_json() or {}
    
    try:
        patient = svc.register_patient(
            name                  = data.get("name", ""),
            age                   = int(data.get("age", 0)),
            gender                = data.get("gender", ""),
            condition             = data.get("condition", ""),
            priority              = int(data.get("priority", 0)),
            ai_suggested_priority = int(data.get("ai_suggested_priority", 0)),
            ai_reasoning          = data.get("ai_reasoning", "")
        )
        return jsonify({"success": True, "patient": patient.to_dict()}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@patient_bp.route("/patients", methods=["GET"])
def api_get_patients():
    """Get all waiting patients sorted by priority."""
    patients = svc.get_waiting_queue()
    return jsonify({"patients": patients, "count": len(patients)}), 200

@patient_bp.route("/patients/admit-next", methods=["POST"])
def api_admit_next():
    """Admit the highest-priority patient from the queue."""
    try:
        patient = svc.admit_next_patient()
        return jsonify({
            "admitted"           : patient.to_dict(),
            "remaining_in_queue" : svc._queue.size()
        }), 200
    except IndexError:
        return jsonify({"error": "Queue is empty"}), 404

@patient_bp.route("/patients/<patient_id>/priority", methods=["PUT"])
def api_update_priority(patient_id):
    """Update a patient's priority."""
    data = request.get_json() or {}
    
    try:
        new_priority = int(data.get("new_priority", 0))
        found = svc.update_priority(patient_id, new_priority)
        if not found:
            return jsonify({"error": "Patient not found"}), 404
        return jsonify({"success": True, "updated_priority": new_priority}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@patient_bp.route("/patients/<patient_id>", methods=["DELETE"])
def api_delete_patient(patient_id):
    """Remove a patient from the queue."""
    found = svc.remove_patient(patient_id)
    if not found:
        return jsonify({"error": "Patient not found"}), 404
    return jsonify({"success": True}), 200

@patient_bp.route("/stats", methods=["GET"])
def api_stats():
    """Get system statistics."""
    return jsonify(svc.get_stats()), 200

@patient_bp.route("/history", methods=["GET"])
def api_history():
    """Get history of admitted patients."""
    history = svc.get_history()
    return jsonify({"history": history, "count": len(history)}), 200

@patient_bp.route("/patients/all", methods=["GET"])
def api_all_patients():
    """Get all patients regardless of status (admin/debug)."""
    return jsonify({"patients": svc.get_all_patients_db()}), 200
